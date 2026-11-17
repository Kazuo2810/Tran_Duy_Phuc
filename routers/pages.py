"""Router: pages — các endpoint cùng nhóm chức năng.

Ghi chú: module này phục vụ HTML giao diện và kiểm tra route chi tiết model.
"""
from fastapi import APIRouter
from common import *

router = APIRouter()

@router.get('/', include_in_schema=False)
@router.get('/compare', include_in_schema=False)
def home():
    """Phục vụ trang giao diện chính của ứng dụng."""
    return FileResponse(ROOT/'static'/'index.html')


@router.get('/models/{model}', include_in_schema=False)
def model_page(model:str):
    """Kiểm tra mã mô hình rồi phục vụ giao diện chi tiết mô hình."""
    check_model(model); return home()

