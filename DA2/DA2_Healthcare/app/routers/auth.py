import os
import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, insert, update, func
from ..database import engine, app_users, patient_profiles
from ..idp import idp_auth
from ..schemas import RegisterInput, LoginInput
from ..security import current_user, ACCESS_COOKIE, CSRF_COOKIE
from ..audit import record

router = APIRouter(prefix="/api", tags=["Xác thực"])
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1" if os.getenv("RENDER") else "0") == "1"


def _new_patient_profile(user_id: str, name: str):
    with engine.begin() as con:
        exists = con.execute(select(patient_profiles.c.id).where(patient_profiles.c.user_id == user_id)).first()
        if not exists:
            con.execute(insert(patient_profiles).values(
                id=str(uuid.uuid4()), user_id=user_id,
                patient_code="P-" + secrets.token_hex(4).upper(),
                full_name=(name or "Bệnh nhân").strip()[:150],
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
            ))


def _ensure_local_user(idp_user: dict):
    user_id = str(idp_user["id"])
    username = str(idp_user["username"]).lower()
    display_name = str(idp_user.get("name") or username)
    with engine.begin() as con:
        row = con.execute(select(app_users).where(app_users.c.id == user_id)).mappings().first()
        if row:
            con.execute(update(app_users).where(app_users.c.id == user_id).values(username=username, display_name=display_name))
            role = row["role"]
            status = row["status"]
        else:
            con.execute(insert(app_users).values(
                id=user_id, username=username, display_name=display_name,
                role="patient", status="active", created_at=datetime.now(timezone.utc),
            ))
            role = "patient"
            status = "active"
    if role == "patient":
        _new_patient_profile(user_id, display_name)
    return {"id": user_id, "username": username, "name": display_name, "role": role, "status": status, "idp_is_admin": bool(idp_user.get("is_admin", False))}


def _set_session(response: Response, auth_result: dict, user: dict):
    csrf = secrets.token_urlsafe(32)
    max_age = int(auth_result.get("expires_in", 28800))
    response.set_cookie(ACCESS_COOKIE, auth_result["access_token"], max_age=max_age,
                        httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/")
    response.set_cookie(CSRF_COOKIE, csrf, max_age=max_age,
                        httponly=False, secure=COOKIE_SECURE, samesite="lax", path="/")
    return {"user": user, "csrf": csrf, "expires_in": max_age}


@router.post("/register", status_code=201)
@router.post("/auth/register", status_code=201)
async def register(payload: RegisterInput, response: Response):
    auth_result = await idp_auth("/api/auth/register", payload.model_dump())
    user = _ensure_local_user(auth_result["user"])
    if user["status"] != "active":
        raise HTTPException(403, "Tài khoản Healthcare đã bị vô hiệu hóa.")
    if user["role"] != "patient":
        raise HTTPException(409, "Tài khoản đã được cấp vai trò khác trong Healthcare.")
    record(user["id"], "account_registered", "app_user", user["id"])
    return {"message": "Tạo tài khoản bệnh nhân thành công.", **_set_session(response, auth_result, user)}


@router.post("/login")
@router.post("/auth/login")
async def login(payload: LoginInput, response: Response):
    auth_result = await idp_auth("/api/auth/login", payload.model_dump())
    user = _ensure_local_user(auth_result["user"])
    if user["status"] != "active":
        raise HTTPException(403, "Tài khoản Healthcare đã bị vô hiệu hóa.")
    record(user["id"], "login", "app_user", user["id"])
    return _set_session(response, auth_result, user)


@router.get("/me")
@router.get("/auth/me")
def me(request: Request, user=Depends(current_user)):
    return {"user": user, "csrf": request.cookies.get(CSRF_COOKIE, "")}


@router.post("/logout")
@router.post("/auth/logout")
def logout(response: Response, user=Depends(current_user)):
    record(user["id"], "logout", "app_user", user["id"])
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"message": "Đã đăng xuất."}


@router.post("/admin/bootstrap")
def bootstrap_admin(user=Depends(current_user)):
    if not user["idp_is_admin"]:
        raise HTTPException(403, "Cần tài khoản quản trị IdP để khởi tạo Admin Healthcare đầu tiên.")
    with engine.begin() as con:
        count = con.execute(select(func.count()).select_from(app_users).where(app_users.c.role == "admin")).scalar_one()
        if count:
            raise HTTPException(409, "Healthcare đã có Admin. Không thể khởi tạo lại.")
        con.execute(update(app_users).where(app_users.c.id == user["id"]).values(role="admin"))
    record(user["id"], "bootstrap_admin", "app_user", user["id"])
    return {"message": "Tài khoản đã được cấp quyền Admin Healthcare. Hãy đăng nhập lại để làm mới thông tin."}
