"""JWT verification and application-level role/assignment authorization."""
import os
import secrets
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
import jwt
from sqlalchemy import select
from .database import engine, app_users, staff_profiles, patient_profiles, staff_patient_assignments

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
IDP_ISSUER = os.getenv("IDP_ISSUER", "https://iris-auth-service.onrender.com").rstrip("/")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "healthcare-web")
OAUTH_REQUIRED_SCOPE = os.getenv("OAUTH_REQUIRED_SCOPE", "healthcare:access")
ACCESS_COOKIE = "healthcare_access"
CSRF_COOKIE = "healthcare_csrf"


def current_user(request: Request) -> dict:
    token = request.cookies.get(ACCESS_COOKIE, "")
    if not token:
        raise HTTPException(401, "Vui lòng đăng nhập.")
    if not JWT_SECRET:
        raise HTTPException(503, "Healthcare chưa được cấu hình JWT_SECRET.")
    try:
        claims = jwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALGORITHM], audience=OAUTH_CLIENT_ID,
            issuer=IDP_ISSUER,
            options={"require": ["exp", "iat", "iss", "sub", "aud", "client_id", "scope"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token đăng nhập không hợp lệ.")

    scopes = claims.get("scope", [])
    if isinstance(scopes, str):
        scopes = scopes.split()
    if claims.get("client_id") != OAUTH_CLIENT_ID or OAUTH_REQUIRED_SCOPE not in scopes:
        raise HTTPException(403, "Token không có quyền truy cập Healthcare.")

    if request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not csrf_cookie or not secrets.compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(403, "CSRF token không hợp lệ.")

    with engine.connect() as con:
        row = con.execute(select(app_users).where(app_users.c.id == str(claims["sub"]))).mappings().first()
    if not row or row["status"] != "active":
        raise HTTPException(403, "Tài khoản chưa được kích hoạt trong Healthcare.")
    return {
        "id": row["id"], "username": row["username"], "name": row["display_name"],
        "role": row["role"], "idp_is_admin": bool(claims.get("is_admin", False)),
        "client_id": claims["client_id"], "scope": scopes,
    }


def require_roles(*roles):
    def dependency(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Bạn không có quyền thực hiện chức năng này.")
        return user
    return dependency


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Chỉ quản trị viên Healthcare được truy cập.")
    return user


def get_patient_for_user(user: dict):
    with engine.connect() as con:
        return con.execute(select(patient_profiles).where(patient_profiles.c.user_id == user["id"])).mappings().first()


def can_access_patient(user: dict, patient_id: str, *, allow_patient=True) -> bool:
    if user["role"] == "admin":
        return True
    with engine.connect() as con:
        if allow_patient and user["role"] == "patient":
            own = con.execute(select(patient_profiles.c.id).where(
                patient_profiles.c.id == patient_id, patient_profiles.c.user_id == user["id"]
            )).first()
            if own:
                return True
        if user["role"] == "staff":
            staff = con.execute(select(staff_profiles.c.id).where(staff_profiles.c.user_id == user["id"])).scalar_one_or_none()
            if staff:
                assigned = con.execute(select(staff_patient_assignments.c.id).where(
                    staff_patient_assignments.c.staff_id == staff,
                    staff_patient_assignments.c.patient_id == patient_id,
                    staff_patient_assignments.c.status == "active",
                )).first()
                return bool(assigned)
    return False


def require_patient_access(patient_id: str, user: dict, *, allow_patient=True):
    if not can_access_patient(user, patient_id, allow_patient=allow_patient):
        # Trả 404 để không tiết lộ sự tồn tại của hồ sơ ngoài phạm vi.
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc bạn không được phân quyền.")
    return user
