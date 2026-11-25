"""
Router: auth — Xử lý xác thực và quản lý phiên người dùng.
Đóng vai trò Proxy chuyển tiếp yêu cầu đăng ký/đăng nhập tới dịch vụ Identity Provider (IdP) độc lập.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from common import *

router = APIRouter()


class RegisterInput(BaseModel):
    """Schema kiểm tra và chuẩn hóa dữ liệu đăng ký tài khoản mới."""
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('username')
    @classmethod
    def clean_username(cls, value):
        # Chuẩn hóa về chữ thường, loại bỏ khoảng trắng thừa và kiểm tra ký tự hợp lệ
        value = value.strip().lower()
        if not 3 <= len(value) <= 80 or not all(c.isalnum() or c in '._-' for c in value):
            raise ValueError('Tên đăng nhập từ 3–80 ký tự, gồm chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.')
        return value

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Họ tên không được để trống.')
        return value


class LoginInput(BaseModel):
    """Schema dữ liệu đăng nhập."""
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


async def call_idp(path: str, payload: dict):
    """
    Hàm tiện ích bất đồng bộ gửi HTTP POST request tới dịch vụ IdP bên ngoài.
    Kèm theo header xác thực của client ứng dụng và xử lý các lỗi mạng/timeout.
    """
    headers = idp_client_headers()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{AUTH_SERVICE_URL}{path}", json=payload, headers=headers)
        
        # Chuyển tiếp mã lỗi và thông báo chi tiết nếu IdP từ chối yêu cầu
        if response.status_code not in (200, 201):
            try:
                detail = response.json().get('detail', 'Yêu cầu xác thực không thành công.')
            except ValueError:
                detail = 'IdP trả về phản hồi không hợp lệ.'
            raise HTTPException(response.status_code, detail)
            
        return response.json()
    except httpx.TimeoutException:
        raise HTTPException(504, 'Trung tâm xác thực phản hồi quá thời gian.')
    except httpx.RequestError:
        raise HTTPException(503, 'Không kết nối được Trung tâm Xác thực Danh tính.')


@router.post('/api/auth/register', status_code=201, tags=['Tài khoản'], summary='Đăng ký tài khoản qua IdP')
async def register(data: RegisterInput):
    """Chuyển tiếp thông tin đăng ký tài khoản sang IdP."""
    return await call_idp('/api/auth/register', data.model_dump())


@router.post('/api/auth/login', tags=['Tài khoản'], summary='Đăng nhập qua IdP')
async def login(data: LoginInput):
    """Chuyển tiếp thông tin đăng nhập sang IdP để nhận token truy cập."""
    return await call_idp('/api/auth/login', data.model_dump())


@router.get('/api/auth/me', tags=['Tài khoản'], summary='Thông tin tài khoản hiện tại')
def auth_me(who=Depends(session)):
    """Giải mã session/token hiện tại và trả về thông tin hồ sơ người dùng đang đăng nhập."""
    return {
        'user': {
            'id': who['id'],
            'username': who['username'],
            'name': who['name'],
            'is_admin': who['is_admin'],
            'client_id': who['client_id']
        }
    }


@router.post('/api/auth/logout', tags=['Tài khoản'], summary='Đăng xuất')
def logout():
    """Endpoint thông báo đăng xuất (việc xóa token được xử lý ở phía client)."""
    return {'message': 'Đã đăng xuất.'}
