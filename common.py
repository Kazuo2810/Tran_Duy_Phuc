"""Thư viện cấu hình và các hàm dùng chung cho toàn bộ các router của Web Service Iris.

Chức năng chính:
- Nạp sẵn các mô hình SVM đã huấn luyện (.joblib) và báo cáo đánh giá (.json) vào RAM.
- Cung cấp các hàm kiểm tra tính hợp lệ của mô hình và khoảng thời gian lọc dữ liệu.
- Xác thực phiên đăng nhập người dùng bằng cách giải mã JWT do IdP cấp (middleware/dependency).
- Truy vấn lịch sử dự đoán tổng hợp từ nhiều bảng SQL theo phân quyền chủ sở hữu.
"""
# === 1. THƯ VIỆN VÀ CẤU HÌNH ===
import os, json, secrets, hashlib, hmac, base64, time, uuid, logging
from pathlib import Path
from datetime import datetime, date, time as daytime, timedelta, timezone
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from functools import lru_cache
from io import BytesIO, StringIO
import csv
import httpx
import joblib
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, insert, delete, update, text, func, union_all
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from sklearn.datasets import load_iris

import database as db
from train import MODEL_NAMES, FEATURES, LABELS, ROOT
from visuals import decision, tree_image, margin_image


# --- 2. NẠP MÔ HÌNH VÀ BÁO CÁO ĐÁNH GIÁ VÀO BỘ NHỚ ---
# Lưu ý: Nạp 'deployment.joblib' (mô hình đã huấn luyện trên toàn bộ 150 mẫu Iris)
MODELS, REPORTS = {}, {}
for key in MODEL_NAMES:
    folder = ROOT / 'models' / key
    if (folder / 'deployment.joblib').exists() and (folder / 'report.json').exists():
        MODELS[key] = joblib.load(folder / 'deployment.joblib')
        REPORTS[key] = json.loads((folder / 'report.json').read_text(encoding='utf-8'))

# Múi giờ Việt Nam để quy đổi ngày lọc báo cáo chính xác theo giờ địa phương
VN = ZoneInfo('Asia/Ho_Chi_Minh')
# Khóa bí mật dùng để ký chữ ký xác thực khi xuất file (nếu cần)
SECRET = os.getenv('EXPORT_SECRET', secrets.token_hex(32)).encode()


# --- 3. HÀM KIỂM TRA MÔ HÌNH & THỜI GIAN ---
def check_model(model: str) -> str:
    """Kiểm tra mã mô hình có nằm trong danh sách 5 cấu hình SVM hỗ trợ hay không."""
    if model not in MODEL_NAMES:
        raise HTTPException(404, 'Model không hợp lệ.')
    return model


def require_model(model: str):
    """Đảm bảo mô hình hợp lệ và đã có file trọng số sẵn sàng trong bộ nhớ."""
    check_model(model)
    if model not in MODELS:
        raise HTTPException(503, 'Model chưa sẵn sàng. Hãy chạy train.py.')
    return MODELS[model]


def date_bounds(start: date | None, end: date | None) -> tuple[str | None, str | None]:
    """Chuyển đổi khoảng ngày (YYYY-MM-DD theo giờ VN) sang chuỗi mốc thời gian UTC ISO 8601."""
    if start and end and start > end:
        raise HTTPException(422, 'Ngày bắt đầu phải không sau ngày kết thúc.')
    # Bắt đầu từ 00:00:00 ngày start
    lower = datetime.combine(start, daytime.min, VN).astimezone(timezone.utc).isoformat() if start else None
    # Kết thúc trước 00:00:00 của ngày (end + 1) để lấy trọn vẹn cả ngày end
    upper = datetime.combine(end + timedelta(days=1), daytime.min, VN).astimezone(timezone.utc).isoformat() if end else None
    return lower, upper


def public_log(row: dict) -> dict:
    """Ẩn trường 'owner' (UUID nội bộ) trước khi trả dữ liệu lịch sử về cho frontend."""
    return {k: v for k, v in row.items() if k != 'owner'}


# --- 4. CẤU HÌNH KẾT NỐI & XÁC THỰC VỚI DỊCH VỤ IDP ---
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET")
JWT_ALGORITHM = "HS256"
IDP_ISSUER = os.getenv("IDP_ISSUER", "http://127.0.0.1:8001").rstrip("/")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "iris-web-local")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")
OAUTH_REQUIRED_SCOPE = os.getenv("OAUTH_REQUIRED_SCOPE", "iris:access")


def idp_client_headers() -> dict:
    """Tạo header định danh Web Service khi gọi API sang server IdP."""
    if not OAUTH_CLIENT_SECRET:
        raise HTTPException(503, "Web Service chưa được cấu hình OAUTH_CLIENT_SECRET.")
    return {"X-Client-ID": OAUTH_CLIENT_ID, "X-Client-Secret": OAUTH_CLIENT_SECRET}


def public_user(row: dict) -> dict:
    """Chuẩn hóa thông tin tài khoản an toàn để hiển thị ra ngoài."""
    return {**{key: row[key] for key in ('id', 'username', 'name')}, 'is_admin': bool(row.get('is_admin', False))}


def session(x_session_token: str = Header(default='')) -> dict:
    """Dependency xác thực người dùng qua header 'X-Session-Token' (chứa JWT).

    Kiểm tra:
    1. Chữ ký JWT và thời hạn sử dụng (exp).
    2. Nguồn phát hành (iss) khớp với IDP_ISSUER và đối tượng nhận (aud) khớp với OAUTH_CLIENT_ID.
    3. Token có chứa quyền 'iris:access' (OAUTH_REQUIRED_SCOPE) hay không.
    """
    if not x_session_token:
        raise HTTPException(401, 'Vui lòng đăng nhập.')
    try:
        payload = jwt.decode(
            x_session_token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=OAUTH_CLIENT_ID,
            issuer=IDP_ISSUER,
            options={"require": ["exp", "iat", "iss", "sub", "aud", "client_id", "scope"]},
        )
        scopes = payload.get('scope', [])
        if isinstance(scopes, str):
            scopes = scopes.split()
        if OAUTH_REQUIRED_SCOPE and OAUTH_REQUIRED_SCOPE not in scopes:
            raise HTTPException(403, 'Token không có quyền truy cập Web Service này.')
        if payload.get('client_id') != OAUTH_CLIENT_ID:
            raise HTTPException(401, 'Token được cấp cho Web Service khác.')
        return {
            'id': payload['sub'],
            'username': payload['username'],
            'name': payload['name'],
            'is_admin': payload['is_admin'],
            'client_id': payload['client_id'],
            'scope': scopes,
            'owner': payload['sub'],  # Dùng UUID người dùng làm khóa phân tách dữ liệu
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, 'Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.')
    except jwt.InvalidTokenError:
        raise HTTPException(401, 'Phiên đăng nhập không hợp lệ.')


def require_admin(who: dict = Depends(session)) -> dict:
    """Dependency kiểm tra quyền Quản trị viên (Admin)."""
    if not who['is_admin']:
        raise HTTPException(403, 'Chỉ tài khoản quản trị được truy cập.')
    return who


# --- 5. TRUY VẤN DỮ LIỆU LỊCH SỬ ---
def query_rows(owner: str, model: str | None = None, user: str | None = None, start: date | None = None, end: date | None = None) -> list[dict]:
    """Truy vấn lịch sử dự đoán của một người dùng (owner) từ 1 hoặc cả 5 bảng log SVM.

    Kết quả được gộp lại và sắp xếp giảm dần theo thời gian dự đoán mới nhất.
    """
    if model:
        check_model(model)
    lower, upper = date_bounds(start, end)
    rows = []
    with db.engine.connect() as con:
        for key in ([model] if model else MODEL_NAMES):
            table = db.logs[key]
            q = select(table).where(table.c.owner == owner)
            if user:
                q = q.where(table.c.user == user)
            if lower:
                q = q.where(table.c.time >= lower)
            if upper:
                q = q.where(table.c.time < upper)
            rows.extend(dict(r) for r in con.execute(q).mappings())

    # Sắp xếp giảm dần theo thời gian (time), nếu trùng thời gian thì xếp theo ID
    rows.sort(key=lambda r: (r['time'], r['id']), reverse=True)
    return [public_log(row) for row in rows]
