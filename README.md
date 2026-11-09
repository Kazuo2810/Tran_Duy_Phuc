# Hệ thống nhận diện hoa Iris – 5 mô hình SVM và xác thực tập trung IdP

## 1. Giới thiệu

Dự án xây dựng hệ thống nhận diện loài hoa Iris bằng 5 cấu hình Support Vector Machine (SVM), kết hợp ứng dụng web FastAPI, cơ sở dữ liệu lưu tài khoản/lịch sử dự đoán và dịch vụ xác thực danh tính tập trung (Identity Provider – IdP).

Mã nguồn được chia thành các module theo chức năng để dễ đọc, trình bày, kiểm thử và bảo trì. Việc tách file không làm mất chức năng: các router vẫn được đăng ký vào ứng dụng FastAPI chính; giao diện vẫn sử dụng HTML, CSS và JavaScript nhưng được tổ chức thành các file riêng.

## 2. Năm mô hình học máy

| Mã | Tên mô hình | Cấu hình chính |
|---|---|---|
| `SVM` | SVM Linear | `kernel=linear`, `C=1.0` |
| `SVM_RBF` | SVM RBF | `kernel=rbf`, `C=1.0`, `gamma=scale` |
| `SVM_POLY` | SVM Polynomial | `kernel=poly`, `degree=3`, `C=1.0` |
| `SVM_SIG` | SVM Sigmoid | `kernel=sigmoid`, `C=1.0`, `gamma=scale` |
| `SVM_OPT` | SVM RBF tối ưu | `GridSearchCV` tìm `C` và `gamma` bằng 5-fold cross-validation |

Tất cả mô hình sử dụng `StandardScaler` trong pipeline và bộ dữ liệu Iris gồm 4 đặc trưng, 3 lớp. Quy trình đánh giá sử dụng cách chia stratified 80/20 với `random_state=42`; mô hình triển khai được huấn luyện lại trên toàn bộ 150 mẫu.

Kết quả Accuracy của lần huấn luyện được lưu trong `models/<MODEL>/report.json`. Đây là kết quả trên lần chia train/test của bộ dữ liệu Iris, không phải cam kết độ chính xác với mọi dữ liệu thực tế khác.

## 3. Cấu trúc thư mục

```text
iris_svm5_modular/
├── app.py                      # Khởi tạo FastAPI, middleware và đăng ký router
├── common.py                   # Cấu hình chung, nạp model, xác thực phiên và helper
├── train.py                    # Khai báo, huấn luyện và đánh giá 5 mô hình SVM
├── database.py                 # Kết nối cơ sở dữ liệu, khai báo bảng và khởi tạo DB
├── auth_app.py                  # Dịch vụ xác thực danh tính tập trung (IdP)
├── visuals.py                   # Tạo hình ảnh trực quan hóa mô hình
├── routers/
│   ├── auth.py                 # Đăng ký, đăng nhập và thông tin tài khoản
│   ├── admin.py                # Quản trị người dùng và lịch sử toàn hệ thống
│   ├── predictions.py          # Dự đoán đơn, dự đoán hàng loạt và kiểm tra file
│   ├── models.py               # Danh sách mô hình, đánh giá, dữ liệu, biểu đồ và health
│   ├── history.py              # Lịch sử cá nhân, lọc, phân trang và xóa
│   ├── exports.py              # Xuất Excel và định dạng bảng tính
│   └── pages.py                # Phục vụ trang giao diện
├── static/
│   ├── index.html              # Cấu trúc giao diện
│   ├── css/
│   │   └── style.css           # Định dạng giao diện
│   └── js/                     # JavaScript phía trình duyệt
│       ├── app-core.js         # Cấu hình API và logic chính
│       ├── intro.js            # Mẫu nhập, thẻ loài và hiệu ứng giới thiệu
│       └── account-history.js  # Tài khoản, quản trị và lịch sử
├── models/                     # Các model đã huấn luyện và báo cáo
└── requirements.txt            # Các thư viện cần cài đặt
```

> Lưu ý: cần giữ đúng tên file và đường dẫn mà `app.py`/`static/index.html` đang tham chiếu. Tài liệu phân chia module mô tả các file JavaScript theo nhóm; một bản ghi chú cũ lại đề cập `static/js/app.js`. Nếu cấu trúc mã nguồn thực tế khác sơ đồ trên, hãy ưu tiên đường dẫn đang được khai báo trong mã nguồn.

## 4. Chức năng chính và luồng hoạt động

1. **Huấn luyện mô hình (`train.py`):** định nghĩa 5 cấu hình SVM, chia tập train/test, cross-validation, lưu model và báo cáo JSON.
2. **Cơ sở dữ liệu (`database.py`):** quản lý kết nối SQL và các bảng người dùng/lịch sử dự đoán theo mã mô hình.
3. **Xác thực (`auth_app.py`, `routers/auth.py`):** IdP xử lý tài khoản tập trung; backend ứng dụng Iris chuyển tiếp yêu cầu đăng ký/đăng nhập và xác thực token.
4. **Dự đoán (`routers/predictions.py`):** nhận 4 thông số đầu vào, gọi mô hình, trả kết quả và ghi lịch sử; hỗ trợ dự đoán hàng loạt từ CSV/XLSX/JSON theo giới hạn được kiểm tra trong mã.
5. **Đánh giá (`routers/models.py`, `visuals.py`):** cung cấp thông tin mô hình, các chỉ số đánh giá, dữ liệu Iris và ảnh vùng quyết định.
6. **Lịch sử (`routers/history.py`, `routers/admin.py`):** người dùng xem/xóa lịch sử của mình; quản trị viên quản lý người dùng và log toàn hệ thống.
7. **Xuất Excel (`routers/exports.py`):** xuất lịch sử theo bộ lọc và phiếu kết quả hiện tại.
8. **Giao diện (`static/`):** HTML tạo cấu trúc trang, CSS định dạng, JavaScript xử lý tương tác và gọi API.

## 5. Kiến trúc xác thực tập trung IdP

Dự án sử dụng **một Identity Provider (IdP) duy nhất** làm trung tâm xác thực và quản lý tài khoản. Các Web Service không cần tự quản lý mật khẩu người dùng; mỗi dịch vụ được đăng ký thành một OAuth client riêng.

### 5.1. Nguyên tắc hoạt động

- Chỉ chạy một `auth_app.py` làm IdP và sử dụng cơ sở dữ liệu tài khoản chung.
- Mỗi Web Service có một bản đăng ký riêng trong bảng `oauth_clients`, gồm `client_id`, `client_secret`, tên, redirect URI, scope và trạng thái.
- Backend của Web Service gửi `X-Client-ID` và `X-Client-Secret` tới IdP. Không đặt các thông tin bí mật này trong HTML hoặc JavaScript.
- IdP chỉ lưu SHA-256 digest của client secret, không lưu secret dạng rõ.
- JWT có các claim: `iss`, `sub`, `aud`, `client_id`, `scope`, `iat`, `exp`, `jti`.
- Web Service kiểm tra chữ ký, issuer, audience, client ID và scope trước khi chấp nhận token.

### 5.2. Sơ đồ tổng quát

```text
                    ┌──────────────────────┐
                    │      Người dùng      │
                    │      Trình duyệt     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Iris Web Service   │
                    │      FastAPI         │
                    │       5 SVM           │
                    └──────────┬───────────┘
                               │ Backend-to-IdP
                               ▼
                    ┌──────────────────────┐
                    │   Identity Provider  │
                    │      auth_app.py     │
                    │ users + oauth_clients│
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      Database        │
                    │ Tài khoản và dữ liệu │
                    └──────────────────────┘
```

### 5.3. Thêm Web Service mới

Khi thêm một Web Service:

1. Đăng ký một object mới trong `OAUTH_CLIENTS_JSON`.
2. Tạo `client_id` và `client_secret` riêng, không dùng lại secret của dịch vụ khác.
3. Khai báo tên dịch vụ, redirect URI chính xác và các scope tối thiểu cần thiết.
4. Cấu hình backend của dịch vụ mới với `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `AUTH_SERVICE_URL`, `IDP_ISSUER` và `JWT_SECRET` theo cách triển khai hiện tại.

### 5.4. Phạm vi triển khai bảo mật

Kiến trúc hiện tại bổ sung đăng ký client, xác thực backend-to-IdP, audience và scope cho JWT. Đây là cơ chế token client-aware của dự án; **chưa phải triển khai đầy đủ OAuth 2.1/OpenID Connect Authorization Code + PKCE hoặc SSO bằng phiên trình duyệt IdP**.

Nếu cần tích hợp nhiều ứng dụng độc lập theo chuẩn OIDC, có thể phát triển thêm authorization endpoint, callback, `state`, PKCE, discovery và JWKS; đồng thời cân nhắc chữ ký bất đối xứng RS256/ES256 thay vì chia sẻ HS256 secret giữa các dịch vụ.

## 6. Cài đặt và chạy trên máy cá nhân

### 6.1. Cài đặt môi trường

Mở terminal tại thư mục gốc dự án:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Nếu cần tạo lại các mô hình và báo cáo:

```powershell
python train.py
```

Nếu chỉ chạy ứng dụng với các model đã có, giữ nguyên thư mục `models/` và không cần huấn luyện lại.

### 6.2. Chạy IdP và Web Service

Mở **hai terminal** tại thư mục dự án.

**Terminal 1 – IdP:**

```powershell
$env:JWT_SECRET="THAY_BANG_CHUOI_NGAU_NHIEN_DAI_VA_BI_MAT"
$env:IDP_ISSUER="http://127.0.0.1:8001"
$env:OAUTH_CLIENTS_JSON='[{"client_id":"iris-web-local","client_name":"Iris ML Web Service","client_secret":"THAY_BANG_CLIENT_SECRET_NGAU_NHIEN_TREN_24_KY_TU","redirect_uris":["http://127.0.0.1:8000"],"scopes":["iris:access","iris:predict","iris:history"],"active":true}]'
$env:ADMIN_PASSWORD="THAY_MAT_KHAU_ADMIN_MOI"
python -m uvicorn auth_app:app --reload --port 8001
```

**Terminal 2 – Iris Web Service:**

```powershell
$env:JWT_SECRET="THAY_BANG_CHUOI_NGAU_NHIEN_DAI_VA_BI_MAT"
$env:IDP_ISSUER="http://127.0.0.1:8001"
$env:AUTH_SERVICE_URL="http://127.0.0.1:8001"
$env:OAUTH_CLIENT_ID="iris-web-local"
$env:OAUTH_CLIENT_SECRET="THAY_BANG_CLIENT_SECRET_NGAU_NHIEN_TREN_24_KY_TU"
$env:OAUTH_REQUIRED_SCOPE="iris:access"
python -m uvicorn app:app --reload --port 8000
```

Thay các chuỗi mẫu bằng secret riêng, đủ mạnh. Trong cấu hình local ở trên, `JWT_SECRET` và client secret phải được cấu hình khớp giữa hai dịch vụ theo cơ chế xác thực của dự án.

### 6.3. Địa chỉ kiểm tra

- Giao diện Iris: `http://127.0.0.1:8000`
- Swagger của Web Service: `http://127.0.0.1:8000/docs`
- Health của Web Service: `http://127.0.0.1:8000/health`
- Swagger của IdP: `http://127.0.0.1:8001/docs`
- Health của IdP: `http://127.0.0.1:8001/health`

Không mở trực tiếp `index.html` bằng `file://`; hãy chạy FastAPI để các đường dẫn static và API hoạt động đúng.

## 7. Đưa mã nguồn lên GitHub

1. Mở thư mục gốc dự án trong VS Code.
2. Tạo repository GitHub mới hoặc chọn repository hiện có.
3. Đưa toàn bộ mã nguồn cần thiết lên repository, bao gồm `app.py`, `auth_app.py`, `common.py`, `database.py`, `train.py`, `visuals.py`, `routers/`, `static/`, `models/`, `requirements.txt` và file cấu hình triển khai nếu có.
4. Không commit `.env`, mật khẩu, JWT secret, client secret hoặc dữ liệu nhạy cảm.
5. Kiểm tra `.gitignore` đã loại các file môi trường ảo, file `.env`, database local và file tạm hay chưa.

## 8. Triển khai lên Render

### 8.1. Kiến trúc dự kiến

Tài liệu triển khai mô tả mô hình gồm hai Render Web Services và một PostgreSQL dùng chung:

| Thành phần | Vai trò | Start command |
|---|---|---|
| `iris-idp-sso` | IdP, quản lý tài khoản và OAuth clients | `uvicorn auth_app:app --host 0.0.0.0 --port $PORT` |
| `iris-web-svm` | Giao diện Iris, API và 5 mô hình SVM | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| `iris-shared-db` | PostgreSQL dùng chung theo thiết kế triển khai | Cơ sở dữ liệu |

Luồng dự kiến:

```text
Browser → iris-web-svm → iris-idp-sso → PostgreSQL
                 │               │
             5 mô hình SVM    users + oauth_clients
             lịch sử dự đoán  tài khoản tập trung
```

### 8.2. Các bước triển khai

1. Đưa mã nguồn lên GitHub.
2. Đăng nhập Render, chọn **New + → Blueprint** nếu repository có `render.yaml`.
3. Kết nối repository và kiểm tra các tài nguyên Render được khai báo trước khi xác nhận tạo.
4. Nếu tên service đã được sử dụng, đổi tên trong cấu hình và cập nhật các URL liên quan.
5. Sau khi Render cấp URL thực tế, cập nhật các biến môi trường để `IDP_ISSUER` và `AUTH_SERVICE_URL` trỏ đúng đến IdP.

### 8.3. Biến môi trường

Các biến dưới đây được mô tả trong tài liệu triển khai. Tên và giá trị thực tế phải đối chiếu với `render.yaml` và mã nguồn hiện tại trước khi deploy.

**Tại IdP (`iris-idp-sso`):**

- `JWT_SECRET`: chuỗi ngẫu nhiên mạnh, tối thiểu 32 bytes.
- `ADMIN_PASSWORD`: mật khẩu quản trị mạnh.
- `OAUTH_CLIENTS_JSON`: danh sách client được phép kết nối. Ví dụ cấu trúc:

```json
[{"client_id":"iris-web-svm","client_name":"Iris SVM Web","client_secret":"THAY_BANG_CLIENT_SECRET_NGAU_NHIEN_DAI_TREN_24_KY_TU","redirect_uris":["https://iris-web-svm.onrender.com"],"scopes":["iris:access","iris:predict","iris:history"],"active":true}]
```

**Tại Iris Web Service (`iris-web-svm`):**

- `JWT_SECRET`: theo tài liệu cấu hình hiện tại, phải giống giá trị ở IdP.
- `OAUTH_CLIENT_ID`: ID client đã đăng ký tại IdP.
- `OAUTH_CLIENT_SECRET`: phải khớp client secret đã đăng ký tại IdP.
- `IDP_ISSUER`: URL HTTPS công khai của IdP.
- `AUTH_SERVICE_URL`: URL của IdP.
- `OAUTH_REQUIRED_SCOPE`: scope mà Web Service yêu cầu.
- `DATABASE_URL`: URL database nếu mã nguồn hỗ trợ cấu hình này.
- `EXPORT_SECRET`: secret riêng dùng cho chức năng xuất dữ liệu nếu được mã nguồn yêu cầu.

**Cảnh báo quan trọng về database:** tài liệu phân chia module ghi SQLite được tạo mặc định tại `iris.db` nếu không cấu hình `DATABASE_URL`, trong khi tài liệu Render đề xuất PostgreSQL dùng chung. Cần kiểm tra `database.py` thực tế có hỗ trợ PostgreSQL và cách đọc `DATABASE_URL` trước khi triển khai theo kiến trúc PostgreSQL. Không được mặc định rằng chỉ thêm biến `DATABASE_URL` là ứng dụng đã tương thích PostgreSQL. SQLite trên filesystem tạm của dịch vụ Render có thể mất dữ liệu khi service được thay thế hoặc khởi động lại; cần chọn giải pháp lưu trữ bền vững phù hợp.

**Bảo mật:**

- Không đưa `JWT_SECRET`, `ADMIN_PASSWORD`, `OAUTH_CLIENT_SECRET` hoặc `EXPORT_SECRET` lên GitHub.
- Không đặt client secret trong HTML/JavaScript.
- Mỗi Web Service cần `client_id` và `client_secret` riêng.
- Dùng URL HTTPS ổn định cho IdP trên production.
- PostgreSQL Free có giới hạn và có thể hết hạn theo chính sách của Render; cần xem chính sách hiện hành và sao lưu dữ liệu quan trọng.

### 8.4. Kiểm tra sau khi deploy

Sau khi có URL thực tế, kiểm tra:

- `https://<IDP-DOMAIN>/health`
- `https://<IDP-DOMAIN>/docs`
- `https://<IRIS-WEB-DOMAIN>/`
- `https://<IRIS-WEB-DOMAIN>/health`
- `https://<IRIS-WEB-DOMAIN>/docs`

Sau đó thử lần lượt đăng ký, đăng nhập, dự đoán, xem lịch sử và xuất Excel.

### 8.5. Một số lỗi thường gặp

| Hiện tượng | Nội dung cần kiểm tra |
|---|---|
| Web không kết nối được IdP | `AUTH_SERVICE_URL` có trỏ đúng URL IdP không |
| Token không hợp lệ | `JWT_SECRET` và `IDP_ISSUER` giữa hai dịch vụ có khớp tuyệt đối không |
| Client không hợp lệ | `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` có khớp với `OAUTH_CLIENTS_JSON` không |
| Lỗi database | Kiểm tra driver, định dạng `DATABASE_URL` và khả năng tương thích PostgreSQL của `database.py` |
| Build thất bại | Xem Render → service → Events/Logs và kiểm tra `pip install -r requirements.txt` |
| Giao diện thiếu CSS/JS | Kiểm tra đường dẫn static được mount trong `app.py` và đường dẫn file được gọi trong `index.html` |

## 9. Kiểm tra đã thực hiện

Theo tài liệu cập nhật mô hình, các kiểm tra sau đã được thực hiện trong môi trường phát triển:

- Huấn luyện thành công cả 5 cấu hình SVM.
- API `/api/models` trả về đúng 5 mã SVM.
- API đánh giá của cả 5 mô hình trả HTTP 200.
- API tạo ảnh lát cắt ranh giới của cả 5 mô hình trả PNG/HTTP 200.
- `/health` trả `status: ok` và `database: true`.
- JavaScript giao diện đã được kiểm tra cú pháp bằng Node.js.

Các kết quả trên là kiểm tra trong môi trường hiện tại, **không đồng nghĩa ứng dụng đã được deploy và kiểm thử thành công trên Render**.

## 10. Lưu ý bảo trì

- Giữ nguyên thư mục `models/` và các file model `.joblib` khi chỉ muốn chạy ứng dụng.
- Chạy lại `python train.py` khi muốn huấn luyện và tạo báo cáo mới.
- Giữ phiên bản thư viện tương thích với các model đã lưu trong `requirements.txt`.
- Bảng `logs_svm` cũ tiếp tục được dùng cho SVM Linear theo tài liệu cập nhật database; các bảng log RF, KNN, DT, LR cũ không bị xóa nhưng không còn xuất hiện trong giao diện/API mới.
- Không xóa database cũ nếu chưa sao lưu và chưa xác định dữ liệu cần giữ.
