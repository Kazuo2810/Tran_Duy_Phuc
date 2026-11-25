"""
Router: pages — Phục vụ giao diện người dùng (Single Page Application - SPA).
"""
from fastapi import APIRouter
from common import *

router = APIRouter()


@router.get('/', include_in_schema=False)
@router.get('/compare', include_in_schema=False)
def home():
    """Trả về file HTML chính cho trang chủ và trang so sánh mô hình."""
    return FileResponse(ROOT / 'static' / 'index.html')


@router.get('/models/{model}', include_in_schema=False)
def model_page(model: str):
    """Kiểm tra tên mô hình hợp lệ trước khi trả về giao diện trang chi tiết mô hình."""
    check_model(model)
    return home()
