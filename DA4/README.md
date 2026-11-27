# DA4 – Movie Recommendation System

## 1. Mục tiêu

Xây dựng hệ thống gợi ý phim từ bộ dữ liệu **MovieLens latest-small** của GroupLens Research. Hệ thống kết hợp ba hướng:

1. **Collaborative Filtering (Item-based):** tìm phim có mẫu đánh giá tương tự dựa trên hành vi người dùng.
2. **Content-Based Filtering:** biểu diễn thể loại và tag bằng TF-IDF để tìm phim có nội dung tương đồng.
3. **Hybrid Recommendation:** kết hợp điểm cộng tác, nội dung và mức độ phổ biến để tạo danh sách đề xuất.

## 2. Dữ liệu

Nguồn: https://grouplens.org/datasets/movielens/latest/

Tải: https://files.grouplens.org/datasets/movielens/ml-latest-small.zip

Bản latest-small có khoảng 100 nghìn ratings, 3,6 nghìn tag applications, 9 nghìn phim và 600 người dùng. Khi huấn luyện, chương trình đọc số lượng thực tế từ CSV và ghi vào `artifacts/dataset_summary.json`.

Các tệp chính:
- `ratings.csv`: userId, movieId, rating, timestamp.
- `movies.csv`: movieId, title, genres.
- `tags.csv`: userId, movieId, tag, timestamp.
- `links.csv`: mã tham chiếu IMDb/TMDb.

Thang điểm đánh giá: 0.5–5.0.

## 3. Cấu trúc

```text
DA4/
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── recommender.py
├── training/
│   ├── __init__.py
│   └── train.py
├── static/
│   └── index.html
├── requirements.txt
├── .gitignore
└── README.md
```

Dữ liệu tải về được lưu trong `data/`; mô hình đã huấn luyện nằm trong `artifacts/`. Hai thư mục này không cần commit vào GitHub.

## 4. Cài đặt và huấn luyện trên Windows

Mở terminal trong thư mục `DA4`:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m training.train
```

Sau khi hoàn tất, hệ thống tạo:
- `artifacts/movie_recommender.joblib`
- `artifacts/dataset_summary.json`

## 5. Chạy ứng dụng

```powershell
uvicorn app.main:app --reload --port 8004
```

- Dashboard: http://127.0.0.1:8004
- Swagger: http://127.0.0.1:8004/docs
- Health: http://127.0.0.1:8004/health

## 6. API

| Endpoint | Chức năng |
|---|---|
| `GET /health` | Kiểm tra ứng dụng và model |
| `GET /api/stats` | Thống kê dataset |
| `GET /api/popular` | Danh sách phim phổ biến |
| `GET /api/search?q=toy` | Tìm phim theo tiêu đề |
| `GET /api/recommend/user/{user_id}` | Gợi ý phim theo người dùng |
| `GET /api/recommend/movie/{movie_id}` | Gợi ý phim tương tự |

## 7. Triển khai Render

Repository tổng `Kazuo2810/Tran_Duy_Phuc`:
- Root Directory: `DA4`
- Build Command: `pip install -r requirements.txt && python -m training.train`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/health`

Không cần PostgreSQL để chạy phiên bản đầu: mô hình dùng dữ liệu MovieLens và artifact cục bộ. Không thêm biến Shared Auth khi chưa cấu hình luồng đăng nhập cho DA4.

## 8. Giới hạn và đánh giá

Phiên bản này tập trung vào xây dựng và trình diễn gợi ý phim. Chưa triển khai tài khoản cá nhân, lưu lịch sử tương tác mới, hoặc đánh giá offline đầy đủ bằng Precision@K/Recall@K/NDCG. Không nên tuyên bố các chỉ số chất lượng chưa được tính từ tập test độc lập.

Nguồn dữ liệu: GroupLens Research, University of Minnesota – MovieLens latest-small.
