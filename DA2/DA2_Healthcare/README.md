# Dự án 2 – Healthcare & WDBC (tích hợp Iris Auth)

**Sinh viên:** Trần Duy Phúc – 24CKDL  
**Học phần:** Học máy nâng cao  
**Mô hình:** Breast Cancer Wisconsin Diagnostic (WDBC), so sánh 4 kernel SVM: Linear, RBF, Polynomial và Sigmoid  
**Phạm vi:** Chỉ phục vụ học tập và trình diễn; không phải công cụ chẩn đoán y tế.

## 1. Mục tiêu phiên bản nâng cấp

Giữ lại mô hình WDBC, artifact, metadata, 30 đặc trưng, kiểm tra dữ liệu đầu vào và giao diện hồ sơ từ bản DA2 trước. Nâng cấp hệ thống tài khoản và dữ liệu thành ứng dụng quản lý bệnh nhân có ba vai trò:

- `admin`: quản lý người dùng, vai trò, nhân viên, bệnh nhân, phân công và nhật ký.
- `staff`: quản lý hồ sơ được phân công, tạo ghi chú và chạy dự đoán WDBC cho bệnh nhân được phân công.
- `patient`: đăng nhập bằng tài khoản riêng, xem hồ sơ và lịch sử của chính mình; chỉ tự cập nhật điện thoại, email và địa chỉ.

Tài khoản/mật khẩu được xác thực bởi `iris-auth-service`. Healthcare không lưu mật khẩu. Tài khoản đăng ký mới mặc định có vai trò `patient`; Admin nâng cấp tài khoản lên `staff` hoặc `admin` trong phạm vi Healthcare.

## 2. Kiến trúc triển khai

- `iris-auth-service`: IdP dùng chung, cấp JWT.
- `iris-prediction-app`: Dự án 1, giữ nguyên.
- `healthcare-wdbc-app`: Web Service mới cho Dự án 2.
- PostgreSQL hiện có: dùng chung instance nhưng Healthcare tạo schema riêng `healthcare`.
- Dữ liệu Iris và bảng IdP hiện tại nằm trong schema `public`; ứng dụng Healthcare không tạo hoặc sửa các bảng đó.

## 3. Cấu trúc thư mục

```text
DA2_Healthcare/
├── app/
│   ├── main.py                 # Khởi chạy FastAPI, nạp artifact
│   ├── database.py             # Schema healthcare và các bảng SQLAlchemy
│   ├── security.py             # Xác minh JWT, vai trò và quyền theo phân công
│   ├── idp.py                  # Gọi iris-auth-service từ backend
│   ├── audit.py                # Ghi nhật ký hoạt động
│   ├── schemas.py              # Pydantic request schemas
│   └── routers/
│       ├── auth.py             # Đăng ký/đăng nhập qua IdP, bootstrap Admin
│       ├── admin.py            # Quản lý vai trò, nhân viên, phân công, audit
│       ├── patients.py         # Hồ sơ bệnh nhân và patient records
│       ├── predictions.py      # Dự đoán WDBC và lưu lịch sử
│       ├── history.py          # Lịch sử theo quyền truy cập
│       ├── models.py           # Metadata và metrics
│       ├── dashboard.py        # Thống kê tổng quan
│       └── exports.py          # Xuất Excel
├── artifacts/                  # 4 pipeline SVM, metadata và phiên bản mô hình
│   └── models/                  # Mỗi kernel có evaluation.joblib, deployment.joblib, metadata.json
├── scripts/train.py            # Mã huấn luyện gốc, không huấn luyện lúc API start
├── reports/                    # Kết quả thực nghiệm gốc
├── tests/                      # Kiểm thử model, JWT và phân quyền
├── web/index.html              # Khung giao diện
│   └── static/css/style.css     # Giao diện CSS tách riêng
│   └── static/js/app.js         # Tương tác và gọi API tách riêng
├── render.yaml                 # Blueprint riêng của Dự án 2
├── requirements.txt
└── .env.example
```

## 4. Cấu trúc PostgreSQL

Ứng dụng tạo schema `healthcare` và các bảng:

| Bảng | Nhiệm vụ |
|---|---|
| `app_users` | Ánh xạ `sub` từ IdP sang vai trò và trạng thái Healthcare |
| `staff_profiles` | Hồ sơ nhân viên |
| `patient_profiles` | Hồ sơ bệnh nhân, có thể liên kết tài khoản Patient |
| `staff_patient_assignments` | Quan hệ nhiều-nhiều giữa nhân viên và bệnh nhân |
| `patient_records` | Ghi chú/hồ sơ bổ sung dạng JSON |
| `prediction_history` | Đầu vào WDBC, kết quả, xác suất và phiên bản mô hình |
| `audit_logs` | Nhật ký truy cập và thao tác quan trọng |

`app_users.id` lưu claim `sub` từ JWT IdP; không sao chép password hash. Các bảng Healthcare có schema riêng, không trùng bảng `iris_users`, `oauth_clients`, `logs_svm*` của Dự án 1/IdP.

## 5. Quy trình tài khoản

1. Người dùng đăng ký qua `/api/register`; backend chuyển tiếp đến IdP.
2. IdP tạo tài khoản và trả JWT dành cho client `healthcare-web`.
3. Healthcare tạo bản ghi `app_users` mặc định vai trò `patient` và hồ sơ bệnh nhân ban đầu.
4. Admin IdP đầu tiên có thể gọi `POST /api/admin/bootstrap` một lần để trở thành Admin Healthcare đầu tiên.
5. Admin Healthcare nâng tài khoản đã đăng ký lên `staff` và hệ thống tự tạo `staff_profiles`.
6. Admin phân công nhân viên cho bệnh nhân qua `staff_patient_assignments`.

Bệnh nhân tự đăng ký có hồ sơ cá nhân riêng. Admin/Staff cũng có thể tạo hồ sơ bệnh nhân chưa gắn tài khoản; Admin có endpoint liên kết tài khoản bệnh nhân sau.

## 6. Cấu hình IdP cần thực hiện

Tạo OAuth client mới trong bảng `public.oauth_clients` (hoặc cấu hình tương đương qua `OAUTH_CLIENTS_JSON` của IdP). Có thể chạy `python scripts/create_oauth_client.py` ở máy local để sinh secret ngẫu nhiên và câu SQL; không commit hoặc chia sẻ output của lệnh này:

- `client_id`: `healthcare-web`
- `client_name`: `Healthcare WDBC App`
- `scopes`: `["healthcare:access"]`
- `active`: `true`
- `client_secret_hash`: SHA-256 của một client secret ngẫu nhiên tối thiểu 24 ký tự.

Không dùng lại client secret của Iris. Client secret chỉ đặt ở biến môi trường backend `OAUTH_CLIENT_SECRET`, tuyệt đối không đưa vào JavaScript hoặc GitHub.

Healthcare cần các biến môi trường:

```text
DATABASE_URL=<cùng connection string PostgreSQL Render hiện tại>
DB_SCHEMA=healthcare
AUTH_SERVICE_URL=https://iris-auth-service.onrender.com
IDP_ISSUER=https://iris-auth-service.onrender.com
JWT_SECRET=<cùng giá trị JWT_SECRET của IdP>
OAUTH_CLIENT_ID=healthcare-web
OAUTH_CLIENT_SECRET=<secret riêng của Healthcare>
OAUTH_REQUIRED_SCOPE=healthcare:access
COOKIE_SECURE=1
```

**Không commit `.env`, JWT secret, client secret hoặc connection string vào GitHub.**

## 7. Chạy local

Cần Python 3.12 và PostgreSQL hoặc SQLite local.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/train.py
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Để kiểm tra API mô hình cục bộ, `POST /predict` không cần tài khoản và không lưu dữ liệu định danh. Các API quản lý bệnh nhân cần IdP được cấu hình đúng.

## 8. API chính

- `POST /api/register`, `POST /api/login`, `GET /api/me`, `POST /api/logout`
- `GET/POST /api/patients`, `GET/PUT /api/patients/{id}`
- `POST /api/patients/{id}/predict`
- `GET /api/history`, `GET /api/history/{id}`
- `GET /api/admin/users`, `PATCH /api/admin/users/{id}/role`
- `GET /api/admin/staff`, `POST /api/admin/assignments`, `DELETE /api/admin/assignments/{id}`
- `GET /api/models`, `GET /api/models/{model_key}`, `GET /api/dashboard/summary`, `GET /api/export`
- `GET /health`, `GET /metadata`, `GET /docs`

## 9. Phân quyền

- Patient: chỉ xem hồ sơ gắn với `app_users.id` của chính mình.
- Staff: chỉ xem bệnh nhân có assignment `active` với `staff_profiles` của mình.
- Admin: quản lý toàn bộ hồ sơ trong Healthcare.
- Các endpoint ghi dữ liệu yêu cầu JWT cookie HttpOnly và CSRF token.
- Kiểm tra quyền được thực hiện tại backend; ẩn nút giao diện không được xem là cơ chế bảo mật.

## 10. Kiểm thử

```powershell
python -m pytest -q
```

Bộ test bao gồm health/model, tạo tài khoản qua mock IdP, bootstrap Admin, phân công Staff–Patient, cách ly hồ sơ, quyền chỉnh sửa của Patient và CSRF.

## 11. Triển khai Render

Dự án 2 được deploy thành Web Service riêng từ repository GitHub, branch `organize-da1`, root directory `DA2/DA2_Healthcare`. Không đổi branch hoặc rootDir của hai dịch vụ Iris hiện tại.

- Build: `pip install -r requirements.txt && python scripts/train.py` (huấn luyện và tạo đủ 4 artifact SVM trước khi khởi chạy).
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Blueprint: chọn file `DA2/DA2_Healthcare/render.yaml`.

Render database đang dùng chung trong tài khoản hiện có là gói Free và bảng điều khiển hiển thị ngày hết hạn **02/12/2026**. Cần kiểm tra gia hạn/nâng cấp hoặc sao lưu và chuyển dữ liệu trước ngày này; không nên coi dữ liệu trên DB Free là lưu trữ lâu dài.

## 12. Phạm vi và giới hạn

- Huấn luyện và so sánh bốn kernel SVM trên cùng cách chia train/test phân tầng; GridSearchCV tối ưu `recall_macro` chỉ trên tập train. Báo cáo dùng tập test độc lập; artifact triển khai được fit lại trên toàn bộ WDBC.
- Mặc định dự đoán là SVM RBF; người dùng có thể chọn Linear, Polynomial hoặc Sigmoid ở trang dự đoán và dự đoán hàng loạt.
- Giao diện được tách thành `web/index.html`, `web/static/css/style.css` và `web/static/js/app.js`.
- Không chuyển ứng dụng thành công cụ chẩn đoán; kết quả chỉ để minh họa học máy.
- Tài khoản SQLite cũ không được tự động chuyển mật khẩu sang IdP; người dùng cần đăng ký lại hoặc được cấp lại tài khoản. Hồ sơ cũ chỉ nên migrate sau khi xác minh dữ liệu và quyền sở hữu.
- Cần cấu hình OAuth client và các biến môi trường trên Render trước khi kiểm thử đăng nhập trực tuyến.
