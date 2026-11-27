# DA3 - Air Quality Forecast Platform

Dự báo PM2.5 sau 1 giờ cho 12 trạm Beijing Multi-Site bằng Random Forest, Voting Ensemble và Stacking Ensemble.

## Huấn luyện (Windows)
1. Tạo môi trường: `python -m venv .venv`
2. Kích hoạt: `.venv\\Scripts\\Activate.ps1`
3. Cài gói: `pip install -r requirements.txt`
4. Tải dữ liệu: `python training/download_dataset.py`
5. Tạo feature: `python training/prepare_training_data.py`
6. Train và đánh giá: `python training/train_models.py`

## Chạy
`uvicorn app.main:app --reload --port 8100`
Dashboard: http://127.0.0.1:8100/ ; API docs: /docs

## Render
Branch: da3-development; Root Directory: DA3
Build: pip install -r requirements.txt
Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health: /health

Biến môi trường nằm trong .env.example. Phải train để tạo artifacts trước khi deploy. Dashboard hiển thị warming_up nếu chưa đủ 25 giờ dữ liệu; không sinh dự báo giả.
