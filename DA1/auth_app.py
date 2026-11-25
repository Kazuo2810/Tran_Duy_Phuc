"""Trung tâm Xác thực Danh tính (Identity Provider - IdP / SSO) dùng chung.

Kiến trúc bảo mật:
- Hoạt động như một microservice xác thực độc lập (mặc định cổng 8001).
- Mỗi Web Service vệ tinh phải đăng ký cặp (client_id, client_secret) riêng.
- client_secret chỉ được giao tiếp backend-to-backend qua header (X-Client-ID, X-Client-Secret),
  tuyệt đối không để lộ ra trình duyệt người dùng.
- Cấp phát JSON Web Token (JWT) chứa thông tin định danh và phạm vi quyền (scopes).
"""
import os
import json
import uuid
import hmac
import hashlib
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean, insert, select, update
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

# --- 1. CẤU HÌNH BIẾN MÔI TRƯỜNG ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET")
JWT_ALGORITHM = "HS256"
IDP_ISSUER = os.getenv("IDP_ISSUER", "http://127.0.0.1:8001")
DEFAULT_SCOPES = [s for s in os.getenv("OAUTH_DEFAULT_SCOPES", "iris:access").split() if s]

# Khởi tạo kết nối SQLAlchemy (bật check_same_thread=False nếu dùng SQLite)
engine_options = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **engine_options)
metadata = MetaData()
password_hasher = PasswordHasher()  # Sử dụng thuật toán Argon2id để băm mật khẩu

# --- 2. ĐỊNH NGHĨA CẤU TRÚC BẢNG DỮ LIỆU ---
users = Table(
    "iris_users", metadata,
    Column("id", String(36), primary_key=True),                    # UUID người dùng
    Column("username", String(80), nullable=False, unique=True, index=True),
    Column("name", String(80), nullable=False),                    # Tên hiển thị
    Column("password_hash", String(255), nullable=False),          # Mật khẩu đã băm Argon2
    Column("created_at", String(40), nullable=False),              # Thời điểm tạo (ISO 8601 UTC)
    Column("is_admin", Boolean, nullable=False, default=False),    # Cờ phân quyền quản trị viên
)

clients = Table(
    "oauth_clients", metadata,
    Column("client_id", String(120), primary_key=True),            # Mã định danh Web Service
    Column("client_name", String(160), nullable=False),            # Tên hiển thị của dịch vụ
    Column("client_secret_hash", String(64), nullable=False),      # Mã băm SHA-256 của secret
    Column("redirect_uris", String(4000), nullable=False, default="[]"),
    Column("scopes", String(2000), nullable=False, default="[]"),  # Danh sách quyền được cấp
    Column("active", Boolean, nullable=False, default=True),       # Trạng thái kích hoạt dịch vụ
    Column("created_at", String(40), nullable=False),
)
metadata.create_all(engine)

# --- 3. KHỞI TẠO FASTAPI & CORS ---
app = FastAPI(title="Trung tâm Xác thực Danh tính (IdP)", version="2.0.0")
allowed_origins = [
    x.strip()
    for x in os.getenv("IDP_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
    if x.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Client-ID", "X-Client-Secret"],
)


# --- 4. SCHEMAS KIỂM TRA DỮ LIỆU ĐẦU VÀO (PYDANTIC) ---
class RegisterInput(BaseModel):
    """Dữ liệu đầu vào khi đăng ký tài khoản mới."""
    model_config = ConfigDict(extra="forbid")  # Cấm gửi thừa trường lạ
    username: str = Field(min_length=3, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        """Chuẩn hóa username về chữ thường và kiểm tra ký tự hợp lệ."""
        value = value.strip().lower()
        if not 3 <= len(value) <= 80 or not all(c.isalnum() or c in "._-" for c in value):
            raise ValueError("Tên đăng nhập từ 3–80 ký tự, gồm chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        """Loại bỏ khoảng trắng thừa ở họ tên."""
        value = value.strip()
        if not value:
            raise ValueError("Họ tên không được để trống.")
        return value


class LoginInput(BaseModel):
    """Dữ liệu đầu vào khi đăng nhập."""
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


# --- 5. HÀM TIỆN ÍCH BẢO MẬT & CẤP TOKEN ---
def secret_digest(secret: str) -> str:
    """Băm client_secret bằng SHA-256 để lưu và đối chiếu trong DB."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def load_client(client_id: str, client_secret: str) -> dict:
    """Xác thực Web Service gọi tới IdP thông qua client_id và client_secret."""
    if not client_id or not client_secret:
        raise HTTPException(401, "Thiếu thông tin định danh Web Service.")
    with engine.connect() as con:
        row = con.execute(select(clients).where(clients.c.client_id == client_id)).mappings().first()
    if not row or not row["active"]:
        raise HTTPException(401, "Web Service chưa được đăng ký hoặc đã bị vô hiệu hóa.")
    # Dùng hmac.compare_digest để chống tấn công đo thời gian (Timing Attack)
    if not hmac.compare_digest(row["client_secret_hash"], secret_digest(client_secret)):
        raise HTTPException(401, "Thông tin xác thực Web Service không hợp lệ.")
    result = dict(row)
    result["scopes"] = json.loads(result["scopes"] or "[]")
    result["redirect_uris"] = json.loads(result["redirect_uris"] or "[]")
    return result


def require_client(
    x_client_id: str = Header(default="", alias="X-Client-ID"),
    x_client_secret: str = Header(default="", alias="X-Client-Secret"),
):
    """Dependency bắt buộc mọi request đăng ký/đăng nhập phải đến từ Web Service hợp lệ."""
    return load_client(x_client_id, x_client_secret)


def create_jwt_token(user_id: str, username: str, name: str, is_admin: bool, client: dict) -> str:
    """Tạo chuỗi JWT chứa đầy đủ các chuẩn claims (iss, sub, aud, iat, exp, jti)."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": IDP_ISSUER.rstrip("/"),       # Bên phát hành token (IdP)
        "sub": user_id,                      # Định danh duy nhất của người dùng
        "username": username,
        "name": name,
        "is_admin": bool(is_admin),
        "client_id": client["client_id"],
        "aud": client["client_id"],          # Đối tượng nhận token (Web Service cụ thể)
        "scope": client["scopes"],           # Quyền hạn của token
        "iat": now,                          # Thời điểm phát hành
        "exp": now + timedelta(hours=int(os.getenv("ACCESS_TOKEN_HOURS", "8"))),  # Thời điểm hết hạn
        "jti": str(uuid.uuid4()),            # ID duy nhất của token
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def token_response(user_id: str, username: str, name: str, is_admin: bool, client: dict) -> dict:
    """Đóng gói phản hồi JSON chuẩn OAuth2 kèm thông tin người dùng."""
    token = create_jwt_token(user_id, username, name, is_admin, client)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": int(os.getenv("ACCESS_TOKEN_HOURS", "8")) * 3600,
        "token": token,  # Trường dự phòng tương thích với frontend hiện tại
        "client_id": client["client_id"],
        "scope": client["scopes"],
        "user": {"id": user_id, "username": username, "name": name, "is_admin": bool(is_admin)},
    }


# --- 6. SỰ KIỆN KHỞI ĐỘNG & CÁC ENDPOINT API ---
@app.on_event("startup")
def setup_idp():
    """Tự động đồng bộ danh sách OAuth Clients và tài khoản Admin từ biến môi trường khi khởi động."""
    raw = os.getenv("OAUTH_CLIENTS_JSON", "").strip()
    if raw:
        try:
            configured = json.loads(raw)
            if not isinstance(configured, list):
                raise ValueError("OAUTH_CLIENTS_JSON phải là một danh sách JSON.")
            for item in configured:
                client_id = str(item["client_id"]).strip()
                client_secret = str(item["client_secret"])
                if not client_id or len(client_secret) < 24:
                    raise ValueError("Mỗi client cần client_id và client_secret tối thiểu 24 ký tự.")
                values = {
                    "client_id": client_id,
                    "client_name": str(item.get("client_name", client_id))[:160],
                    "client_secret_hash": secret_digest(client_secret),
                    "redirect_uris": json.dumps(item.get("redirect_uris", [])),
                    "scopes": json.dumps(item.get("scopes", DEFAULT_SCOPES)),
                    "active": bool(item.get("active", True)),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                with engine.begin() as con:
                    exists = con.execute(select(clients.c.client_id).where(clients.c.client_id == client_id)).first()
                    if exists:
                        con.execute(
                            update(clients)
                            .where(clients.c.client_id == client_id)
                            .values(**{k: v for k, v in values.items() if k != "created_at"})
                        )
                    else:
                        con.execute(insert(clients).values(**values))
        except Exception as exc:
            raise RuntimeError(f"Cấu hình OAUTH_CLIENTS_JSON không hợp lệ: {exc}") from exc

    # Tạo hoặc cập nhật quyền cho tài khoản Admin mặc định nếu có ADMIN_PASSWORD
    admin_user = os.getenv("ADMIN_USERNAME", "admin").strip().lower()
    admin_pass = os.getenv("ADMIN_PASSWORD", "").strip()
    if admin_pass:
        with engine.connect() as con:
            row = con.execute(select(users).where(users.c.username == admin_user)).mappings().first()
        if not row:
            with engine.begin() as con:
                con.execute(insert(users).values(
                    id=str(uuid.uuid4()),
                    username=admin_user,
                    name=os.getenv("ADMIN_DISPLAY_NAME", "Quản trị viên"),
                    password_hash=password_hasher.hash(admin_pass),
                    created_at=datetime.now(timezone.utc).isoformat(),
                    is_admin=True,
                ))
        elif not row["is_admin"]:
            with engine.begin() as con:
                con.execute(update(users).where(users.c.username == admin_user).values(is_admin=True))


@app.get("/health")
def health():
    """Endpoint kiểm tra tình trạng sống (Health Check) cho nền tảng deploy (Render)."""
    with engine.connect() as con:
        con.execute(select(clients.c.client_id).limit(1)).first()
    return {"status": "ok", "service": "identity-provider"}


@app.get("/api/clients")
def list_clients():
    """Trả về danh sách các Web Service đã đăng ký (tuyệt đối không trả về secret)."""
    with engine.connect() as con:
        rows = con.execute(
            select(clients.c.client_id, clients.c.client_name, clients.c.active, clients.c.created_at)
        ).mappings().all()
    return {"clients": [dict(row) for row in rows]}


@app.post("/api/auth/register", status_code=201)
def register(data: RegisterInput, client=Depends(require_client)):
    """Đăng ký người dùng mới và trả về JWT ngay lập tức."""
    user_id = str(uuid.uuid4())
    row = {
        "id": user_id,
        "username": data.username,
        "name": data.name,
        "password_hash": password_hasher.hash(data.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_admin": False,
    }
    try:
        with engine.begin() as con:
            con.execute(insert(users).values(**row))
    except Exception:
        raise HTTPException(409, "Tên đăng nhập đã tồn tại.")
    return {**token_response(user_id, data.username, data.name, False, client), "message": "Đăng ký tài khoản thành công."}


@app.post("/api/auth/login")
def login(data: LoginInput, client=Depends(require_client)):
    """Kiểm tra thông tin đăng nhập bằng Argon2 và cấp phát JWT."""
    with engine.connect() as con:
        row = con.execute(select(users).where(users.c.username == data.username.strip().lower())).mappings().first()
    invalid = HTTPException(401, "Tên đăng nhập hoặc mật khẩu không đúng.")
    if not row:
        raise invalid
    try:
        password_hasher.verify(row["password_hash"], data.password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        raise invalid
    return {
        **token_response(row["id"], row["username"], row["name"], row["is_admin"], client),
        "message": "Đăng nhập thành công.",
    }
