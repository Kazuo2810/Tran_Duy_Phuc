"""Điểm khởi chạy chính của Web Service FastAPI (Ứng dụng Nhận diện Iris).

Chức năng:
- Khởi tạo cơ sở dữ liệu khi ứng dụng bắt đầu chạy (lifespan).
- Cấu hình bảo mật CORS, phục vụ file tĩnh (/static).
- Bắt và chuẩn hóa thông báo lỗi (Validation & Database).
- Gắn kết toàn bộ các nhóm API (routers) vào ứng dụng chính.

Lệnh chạy cục bộ:
    python -m uvicorn app:app --reload
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from common import ROOT, db
from routers import auth, admin, predictions, models, history, exports, pages


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời ứng dụng: tự động tạo bảng DB trước khi nhận request."""
    db.init_db()
    yield
    # Có thể bổ sung giải phóng tài nguyên khi tắt server tại đây


# Khởi tạo đối tượng ứng dụng FastAPI và phân nhóm tài liệu Swagger UI
app = FastAPI(
    title='Nhận diện Iris — 5 cấu hình SVM',
    lifespan=lifespan,
    openapi_tags=[{'name': name} for name in [
        'Tài khoản', 'Quản trị', 'Dự đoán', 'Mô hình và đánh giá',
        'Dữ liệu', 'Lịch sử', 'Xuất Excel', 'Hệ thống'
    ]],
    swagger_ui_parameters={'docExpansion': 'none', 'filter': True},
)

# Cấu hình CORS (Cross-Origin Resource Sharing) nếu có khai báo biến CORS_ORIGINS
origins = [s.strip() for s in os.getenv('CORS_ORIGINS', '').split(',') if s.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=['GET', 'POST', 'DELETE'],
        allow_headers=['Content-Type', 'X-Session-Token'],
    )

# Gắn thư mục chứa giao diện tĩnh (HTML, CSS, JS, hình ảnh) vào đường dẫn /static
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    """Tùy biến thông báo lỗi HTTP 422 khi dữ liệu đầu vào (Pydantic) sai định dạng."""
    fields = ', '.join(str(e['loc'][-1]) for e in exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            'detail': (
                f'Dữ liệu không hợp lệ tại: {fields}. '
                'Kiểm tra số đo hữu hạn > 0, ngày và các trường yêu cầu.'
            )
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sql_error(request, exc):
    """Bắt lỗi kết nối/truy vấn SQL, ghi log chi tiết và trả về HTTP 503 an toàn."""
    logging.exception('Lỗi database', exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={'detail': 'Không thể truy cập database. Vui lòng thử lại.'},
    )


# Nạp toàn bộ các router chức năng vào ứng dụng chính
for api_router in (
    auth.router,         # Đăng ký, đăng nhập, thông tin người dùng
    admin.router,        # Quản trị hệ thống và tài khoản
    predictions.router,  # Dự đoán loài hoa Iris đơn lẻ và hàng loạt
    models.router,       # Xem chỉ số đánh giá và biểu đồ trực quan mô hình
    history.router,      # Truy vấn và xóa lịch sử dự đoán
    exports.router,      # Xuất dữ liệu/báo cáo ra file Excel
    pages.router,        # Trả về các trang giao diện web HTML
):
    app.include_router(api_router)
