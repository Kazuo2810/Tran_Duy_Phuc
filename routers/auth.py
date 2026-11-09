"""Router chuyển tiếp đăng ký/đăng nhập tới IdP bằng thông tin client riêng."""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from common import *

router = APIRouter()

class RegisterInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    @field_validator('username')
    @classmethod
    def clean_username(cls, value):
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
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)

async def call_idp(path: str, payload: dict):
    headers = idp_client_headers()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{AUTH_SERVICE_URL}{path}", json=payload, headers=headers)
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
    return await call_idp('/api/auth/register', data.model_dump())

@router.post('/api/auth/login', tags=['Tài khoản'], summary='Đăng nhập qua IdP')
async def login(data: LoginInput):
    return await call_idp('/api/auth/login', data.model_dump())

@router.get('/api/auth/me', tags=['Tài khoản'], summary='Thông tin tài khoản hiện tại')
def auth_me(who=Depends(session)):
    return {'user': {'id': who['id'], 'username': who['username'], 'name': who['name'], 'is_admin': who['is_admin'], 'client_id': who['client_id']}}

@router.post('/api/auth/logout', tags=['Tài khoản'], summary='Đăng xuất')
def logout():
    return {'message': 'Đã đăng xuất.'}
