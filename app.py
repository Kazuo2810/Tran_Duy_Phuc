"""Điểm khởi chạy FastAPI. Các endpoint được chia trong thư mục routers/.
Chạy: python -m uvicorn app:app --reload
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
async def lifespan(app):
    db.init_db()
    yield

app = FastAPI(
    title='Nhận diện Iris — 5 cấu hình SVM',
    lifespan=lifespan,
    openapi_tags=[{'name': name} for name in [
        'Tài khoản', 'Quản trị', 'Dự đoán', 'Mô hình và đánh giá',
        'Dữ liệu', 'Lịch sử', 'Xuất Excel', 'Hệ thống'
    ]],
    swagger_ui_parameters={'docExpansion': 'none', 'filter': True},
)

origins = [s.strip() for s in os.getenv('CORS_ORIGINS', '').split(',') if s.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=['GET', 'POST', 'DELETE'],
        allow_headers=['Content-Type', 'X-Session-Token']
    )

app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = ', '.join(str(e['loc'][-1]) for e in exc.errors())
    return JSONResponse(status_code=422, content={
        'detail': 'Dữ liệu không hợp lệ tại: ' + fields +
        '. Kiểm tra số đo hữu hạn > 0, ngày và các trường yêu cầu.'
    })

@app.exception_handler(SQLAlchemyError)
async def sql_error(request, exc):
    logging.exception('Lỗi database', exc_info=exc)
    return JSONResponse(status_code=503, content={
        'detail': 'Không thể truy cập database. Vui lòng thử lại.'
    })

for api_router in (auth.router, admin.router, predictions.router, models.router, history.router, exports.router, pages.router):
    app.include_router(api_router)
