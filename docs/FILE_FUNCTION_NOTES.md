# Ghi chú chi tiết theo file và chức năng

Tài liệu này là bản đồ nhanh của toàn bộ repository. Mỗi mục mô tả trách nhiệm
của file và chức năng chính trong file đó. Các ghi chú không thay đổi luồng
chạy; chúng giúp người đọc biết nên bắt đầu đọc từ đâu và dữ liệu đi qua các
module như thế nào.

## 1. File cấu hình và tài liệu

### `.env.example`

Mẫu biến môi trường cho IdP và Web Service Iris. Các nhóm biến gồm:

- `IDP_ISSUER`, `DATABASE_URL`, `JWT_SECRET`: định danh IdP, cơ sở dữ liệu và
  khóa ký JWT dùng chung.
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`: tài khoản quản trị được tạo khi IdP
  khởi động lần đầu.
- `OAUTH_CLIENTS_JSON`: danh sách client được phép gọi IdP, gồm client ID,
  secret, scope và redirect URI.
- `AUTH_SERVICE_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`,
  `OAUTH_REQUIRED_SCOPE`: cấu hình Web Service khi gọi IdP.

Không commit file `.env` thật; mọi secret trong file mẫu chỉ là placeholder.

### `.gitignore`

Loại khỏi Git các secret, khóa riêng, database cục bộ, cache Python, môi
trường ảo, file IDE và file hệ điều hành. Ngoại lệ `!.env.example` cho phép
giữ lại mẫu cấu hình an toàn.

### `requirements.txt`

Ghim các thư viện runtime, machine learning, SQL, Excel, HTTP, JWT và kiểm
thử. Việc ghim phiên bản giúp model và kết quả đánh giá có thể tái lập.

### `render.yaml`

Khai báo hạ tầng Render:

- `iris-idp-sso`: chạy `auth_app:app`, cung cấp dịch vụ xác thực.
- `iris-web-svm`: chạy `app:app`, cung cấp giao diện và API dự đoán.
- `iris-shared-db`: database dùng chung cho tài khoản và lịch sử.

`sync: false` đánh dấu secret phải được nhập trong dashboard, không ghi trực
tiếp vào repository.

### `README.md`

Tài liệu hướng dẫn tổng quan: kiến trúc, năm cấu hình SVM, luồng xác thực,
cách chạy local, triển khai Render, API và các lưu ý an toàn. Bản ghi chú
chi tiết theo hàm nằm trong file này để README vẫn tập trung vào hướng dẫn
người dùng.

## 2. Backend và machine learning

### `app.py`

Điểm vào của Web Service FastAPI. File này tạo ứng dụng, cấu hình CORS,
mount thư mục static, đăng ký router và chuyển lỗi thành JSON.

- `lifespan(app)`: khởi tạo database trước khi server nhận request; `yield`
  giữ ứng dụng sống trong suốt vòng đời process.
- `validation_error(request, exc)`: chuyển lỗi validation của FastAPI thành
  phản hồi 422 có cấu trúc thống nhất.
- `sql_error(request, exc)`: ghi log lỗi SQL và trả lỗi 500 mà không làm lộ
  câu lệnh hoặc thông tin kết nối.

### `auth_app.py`

Identity Provider tập trung. File lưu user/client trong SQL, băm password bằng
Argon2, băm client secret bằng SHA-256 và phát JWT HS256.

- `RegisterInput.clean_username(value)`: trim, lowercase và chỉ cho phép
  username 3–80 ký tự với chữ, số, `.`, `_`, `-`.
- `RegisterInput.clean_name(value)`: trim họ tên và từ chối giá trị rỗng.
- `secret_digest(secret)`: tạo digest SHA-256 để so sánh client secret mà
  không lưu secret dạng rõ.
- `load_client(client_id, client_secret)`: tìm client, kiểm tra active,
  so sánh secret constant-time và giải mã scope/redirect URI.
- `require_client(...)`: dependency đọc `X-Client-ID` và
  `X-Client-Secret`, sau đó ủy quyền cho `load_client`.
- `create_jwt_token(...)`: tạo claim `iss`, `sub`, `aud`, `client_id`,
  `scope`, `iat`, `exp`, `jti` và trạng thái admin.
- `token_response(...)`: đóng gói access token cùng thông tin user và thời
  hạn để frontend/backend client dùng thống nhất.
- `setup_idp()`: đọc `OAUTH_CLIENTS_JSON`, upsert client và bảo đảm tài khoản
  admin tồn tại hoặc được nâng quyền admin.
- `health()`: kiểm tra IdP truy cập được bảng client.
- `list_clients()`: công khai metadata client, tuyệt đối không trả secret.
- `register(data, client)`: băm password, tạo user mới và cấp token ngay sau
  khi đăng ký thành công.
- `login(data, client)`: tìm user, verify Argon2 password và cấp token.

### `common.py`

Tập trung cấu hình dùng chung, nạp model/report, xác thực session, kiểm tra
scope và các helper dùng bởi mọi router.

- `check_model(model)`: kiểm tra mã model có nằm trong danh sách cho phép.
- `require_model(model)`: kiểm tra rồi trả estimator đã nạp; dùng cho endpoint
  cần model sẵn sàng.
- `date_bounds(start, end)`: đổi bộ lọc ngày thành mốc UTC đầu ngày và ngày
  kế tiếp, giúp truy vấn bao trọn ngày kết thúc.
- `public_log(row)`: loại thông tin nội bộ như owner khỏi log trước khi trả
  cho người dùng.
- `idp_client_headers()`: tạo header client để backend gọi IdP; secret không
  được đưa vào HTML/JavaScript.
- `public_user(row)`: chuyển bản ghi user thành cấu trúc public an toàn.
- `session(x_session_token)`: xác thực JWT/session token, kiểm tra issuer,
  audience, client ID, scope và hạn token.
- `require_admin(who)`: dependency chặn endpoint quản trị nếu session không
  có cờ admin.
- `query_rows(owner, model, user, start, end)`: union log theo model, lọc
  theo chủ sở hữu/bộ lọc và trả dữ liệu đã chuẩn hóa theo thời gian.

### `database.py`

Tạo SQLAlchemy engine và schema cho user, log dự đoán theo từng model. Hỗ trợ
SQLite local và PostgreSQL khi deploy.

- `init_db()`: tạo bảng còn thiếu và thực hiện các bước khởi tạo schema cần
  thiết trước khi ứng dụng chạy.

Các bảng log được sinh theo `MODEL_NAMES`; mỗi bảng giữ input bốn đặc trưng,
model/version, kết quả, thời gian, user và thời gian xử lý.

### `train.py`

Định nghĩa, huấn luyện, đánh giá và lưu năm pipeline SVM cùng report JSON.

- `estimators()`: trả dictionary năm estimator: Linear, RBF, Polynomial,
  Sigmoid và RBF tối ưu bằng GridSearchCV.
- `_json_parameters(estimator, tuned_search)`: lấy tham số estimator/search
  theo kiểu có thể serialize vào JSON, đồng thời ghi best params khi tuning.
- `train_all(output)`: tải Iris, chia stratified train/test, cross-validation,
  đánh giá metric/confusion matrix, fit model triển khai trên toàn bộ dữ liệu
  và ghi `deployment.joblib`, `evaluation.joblib`, `report.json`.

### `visuals.py`

Sinh PNG trực tiếp trong memory cho các biểu đồ model, không tạo file tạm.

- `png(fig)`: serialize matplotlib figure thành bytes PNG rồi đóng figure.
- `decision(model, key, a, b)`: vẽ vùng quyết định trên hai đặc trưng được
  chọn, giữ các đặc trưng còn lại ở median.
- `tree_image(model, key)`: helper tương thích cho trực quan cây; các model
  hiện tại là SVM nên router không cho gọi kiểu này.
- `margin_image()`: vẽ minh họa SVM nhị phân, đường biên và margin.

## 3. Router API

### `routers/__init__.py`

Đánh dấu `routers` là Python package; các router con được import và đăng ký
trong `app.py`.

### `routers/auth.py`

Lớp adapter giữa Web Service và IdP. Client secret chỉ nằm ở backend.

- `RegisterInput.clean_username(value)`: chuẩn hóa username trước khi gửi
  sang IdP.
- `RegisterInput.clean_name(value)`: loại khoảng trắng thừa và chặn tên rỗng.
- `call_idp(path, payload)`: POST tới IdP, xử lý status lỗi, timeout và lỗi
  mạng thành HTTPException phù hợp.
- `register(data)`: chuyển tiếp đăng ký.
- `login(data)`: chuyển tiếp đăng nhập.
- `auth_me(who)`: trả profile của session hiện tại.
- `logout()`: trả thông báo để frontend xóa token cục bộ; JWT stateless không
  cần thao tác xóa server-side.

### `routers/admin.py`

Endpoint quản trị user và toàn bộ lịch sử.

- `admin_users(search, page, size, who)`: tìm user theo username/name và
  phân trang, chỉ trả metadata an toàn.
- `admin_logs(model, user_id, start, end, page, size, who)`: union log của
  một hoặc tất cả model, lọc theo user/ngày và phân trang.
- `AdminLogReference`: mô tả một cặp model/log ID được phép xóa.
- `AdminDeleteLogsInput`: danh sách log cần xóa và cờ xác nhận.
- `admin_delete_logs(data, who)`: kiểm tra toàn bộ ID trước, sau đó xóa trong
  transaction để tránh xóa dở dang.

### `routers/predictions.py`

Nhận input, gọi estimator, lưu log và hỗ trợ dự đoán batch.

- `PredictionInput`: schema bốn số đo dương, finite; cấm field ngoài schema.
- `sign_result(row, owner)`: tạo token export tạm thời chứa row, owner, hạn
  một giờ và chữ ký HMAC.
- `verify_result(token, owner)`: kiểm tra format, chữ ký, owner và expiry
  trước khi cho export.
- `persist_log(model, row)`: insert một bản ghi vào bảng log của model.
- `predict(model, data, user)`: validate model, dự đoán một mẫu, đo latency,
  cố gắng lưu log, tạo cảnh báo ngoài phạm vi train và trả export token.
- `BatchFileInput`: giới hạn tên file và payload base64 để bảo vệ endpoint
  batch.
- `parse_batch_file(data)`: giải mã CSV/XLSX/JSON, kiểm tra kích thước,
  header, số dòng, kiểu dữ liệu và trả danh sách `PredictionInput`.
- `predict_batch(model, data, user)`: dự đoán vectorized, tính latency trung
  bình, insert batch trong transaction và trả kết quả theo dòng nguồn.

### `routers/history.py`

Truy vấn và xóa lịch sử thuộc đúng tài khoản đang đăng nhập.

- `get_logs(...)`: lọc lịch sử theo model/user/ngày và phân trang.
- `model_logs(...)`: kiểm tra model rồi tái sử dụng `get_logs` cho một model.
- `DeleteInput`: schema danh sách tối đa 100 ID và cờ xác nhận.
- `delete_logs(model, data, who)`: kiểm tra mọi ID thuộc owner/model trước
  khi xóa, tránh xóa nhầm hoặc xóa một phần.

### `routers/models.py`

Endpoint trạng thái, report, dataset và ảnh trực quan.

- `health()`: kiểm tra SQL và đủ năm model; trả 200/503 tương ứng.
- `models()`: liệt kê model, tên hiển thị, trạng thái available và report.
- `evaluate(model)`: trả report JSON của model sau khi kiểm tra tồn tại.
- `dataset()`: trả toàn bộ Iris data, labels, classes và min/max.
- `download_sample_data()`: tạo CSV UTF-8 BOM để người dùng tải làm mẫu
  batch.
- `cached_visual(model, kind, x, y)`: cache bytes PNG, chọn loại biểu đồ và
  từ chối loại không phù hợp.
- `visual(model, kind, x, y)`: kiểm tra hai trục khác nhau và trả PNG.
- `importance(model)`: trả feature importance nếu estimator hỗ trợ; SVM
  hiện tại thường trả `None`.

### `routers/exports.py`

Tạo workbook Excel từ log hoặc kết quả hiện tại.

- `style_sheet(ws)`: freeze header, bật filter, tô màu tiêu đề và tự tính
  chiều rộng cột.
- `excel_response(rows)`: tạo sheet tổng hợp, sheet từng model, sheet ghi
  chú timezone/metric/quyền truy cập và trả bytes XLSX.
- `export(model, user, start, end, who)`: xuất log theo filter của owner,
  trả 404 nếu không có dữ liệu.
- `ExportInput`: schema chứa export token đã ký.
- `export_current(data, who)`: verify token rồi xuất một kết quả hiện tại,
  không cho dùng token của owner khác.

### `routers/pages.py`

Phục vụ giao diện HTML.

- `home()`: trả `static/index.html` cho trang gốc và `/compare`.
- `model_page(model)`: kiểm tra model rồi trả cùng giao diện cho route chi
  tiết model.

## 4. Frontend

### `static/index.html`

Cấu trúc giao diện gồm navigation, đăng nhập, dự đoán đơn/batch, đánh giá,
dataset, trực quan, lịch sử, quản trị và modal thông báo. File chỉ chứa
markup/presentation; state và gọi API nằm trong JavaScript.

### `static/css/style.css`

Định nghĩa design token sáng/tối, layout container, navigation, form,
button, table, modal, chart, card và media query responsive. Các comment
`PHẦN` đánh dấu khu vực để chỉnh giao diện mà không ảnh hưởng logic API.

### `static/js/app-core.js`

State và logic dùng chung cho toàn frontend.

- `$`: lấy phần tử DOM theo ID.
- `request(path, options)`: gọi API, tự gắn Bearer token, timeout 45 giây,
  chuẩn hóa JSON/Blob và lỗi.
- `cancelRequests()`: abort các request đang chờ khi đổi model/tab.
- `message(id, text, error)`: hiển thị trạng thái thành công/lỗi.
- `pct(value)`: format metric 0–1 thành phần trăm.
- `table(target, headers, rows)`: dựng bảng bằng DOM textContent, tránh
  chèn HTML không tin cậy.
- `updateProfileUI()`, `showLoginModal()`, `closeLoginModal()`,
  `handleLoginKey(e)`, `login()`: các adapter tương thích với markup/modal.
- `clearIrisSession()`: xóa token và reset profile local.
- `logout()`: gọi logout, luôn dọn session local dù request thất bại.
- `toggleTheme()`: đổi theme và lưu lựa chọn vào localStorage.
- `switchTab(id)`: chuyển section và trạng thái active của navigation.
- `rememberForm()`: lưu input của model hiện tại khi chuyển model.
- `resetResult()`: dọn kết quả dự đoán và thông báo cũ.
- `changeModel(push)`: đổi model, URL, form state, report và ảnh trực quan.
- `loadEvaluation()`: lấy report và render metric/confusion matrix/class report.
- `fillSample(...)`: nạp bốn số đo vào cả input số và range.
- `syncRange(range, value)`: đồng bộ range theo giá trị số hợp lệ.
- `resetForm()`: nạp mẫu Iris mặc định và dọn kết quả.
- `resetBatchResult()`: xóa kết quả batch và khóa nút download.
- `submitBatchPrediction()`: đọc file, base64 hóa, gọi API batch và render
  từng dòng kết quả.
- `downloadBatchResults()`: serialize kết quả batch thành CSV có BOM.
- `submitPrediction()`: validate bốn input, gọi API đơn, render prediction,
  warning, thời gian và trạng thái lưu.
- `filters(all)`: tạo query string filter history/admin.
- `resetFilters()`: xóa bộ lọc và tải lại trang đầu.
- `loadLogs(page)`: lấy log cá nhân, render checkbox và phân trang.
- `clearHistory()`: gửi các ID đang chọn để xóa sau khi xác nhận.
- `download(blob, name)`: tạo object URL, kích hoạt tải xuống rồi revoke URL.
- `exportToExcel(all)`: gọi endpoint export và tải workbook.
- `exportCurrent()`: tải riêng kết quả hiện tại bằng export token.
- `loadComparison()`: lấy danh sách model và dựng bảng so sánh metric.
- `setPlot(id, path, e, ve)`: tải ảnh trực quan, bỏ qua response cũ khi
  epoch đã thay đổi.
- `loadVisual()`: tải decision/margin plot và feature importance cho model.
- `canvas(id)`: chuẩn bị canvas có kích thước, font, màu theo theme.
- `drawData()`: vẽ biểu đồ số lượng class và scatter plot dataset.
- `downloadSampleData()`: tải CSV mẫu từ API.
- `loadData()`: lấy dataset rồi gọi `drawData`.
- `health()`: hiển thị trạng thái API/SQL và số model sẵn sàng.

### `static/js/account-history.js`

Logic tài khoản, quản trị và lựa chọn lịch sử.

- `setIrisAuthMode(mode)`: chuyển form login/register và cập nhật required
  fields/autocomplete.
- `openIrisAuth(mode)`: mở modal, lưu focus cũ và focus username.
- `closeIrisAuth()`: đóng modal, xóa password và trả focus.
- `renderIrisAccount()`: render trạng thái user, nút logout/copy ID hoặc
  login/register; ẩn tab admin nếu không có quyền.
- `restoreIrisSession()`: xác minh token đã lưu và khôi phục profile.
- `submitIrisAuth()`: validate form, gửi login/register, lưu token và cập
  nhật giao diện.
- `adminTime(value)`: format timestamp theo múi giờ Việt Nam.
- `adminPaging(kind, result)`: cập nhật label và trạng thái nút phân trang.
- `loadAdminUsers(page)`: tải danh sách user quản trị và render bảng.
- `loadAdminLogs(page)`: tải log toàn hệ thống theo filter và render bảng.
- `syncAdminSelection()`: đồng bộ checkbox chọn tất cả và số lượng đã chọn.
- `renderAdminLogs(items)`: dựng bảng log kèm checkbox model/ID.
- `deleteAdminLogs()`: xác nhận, gom các log đã chọn và gọi API xóa admin.
- `visibleHistoryChecks()`: lấy checkbox log cá nhân đang hiển thị.
- `syncHistorySelection()`: cập nhật trạng thái chọn tất cả và counter.
- DOMContentLoaded handler: nối submit, modal, Escape/Tab focus trap và
  MutationObserver cho bảng lịch sử.

### `static/js/intro.js`

Nội dung trang giới thiệu và mẫu dữ liệu minh họa.

- `applyUploadedSample(value)`: kiểm tra object có đủ bốn số đo dương finite
  rồi nạp vào form/range.
- `selectIntroSpecies(i)`: đổi thẻ loài, mô tả, trạng thái aria và mẫu đo
  minh họa.
- DOMContentLoaded handler: nạp mẫu mặc định và tạo hiệu ứng cánh hoa.

## 5. Model artifacts và report

Mỗi thư mục `models/<MODEL>/` chứa:

- `deployment.joblib`: pipeline đã fit trên toàn bộ 150 mẫu, dùng cho dự đoán
  production.
- `evaluation.joblib`: estimator/evaluation artifact phục vụ kiểm tra hoặc
  tái sử dụng.
- `report.json`: metric của lần train/test 120/30, cross-validation, confusion
  matrix, feature range, tham số và version. Trường `_comment` giải thích
  artifact; nó không ảnh hưởng các trường metric mà backend đọc.

Các model gồm `SVM`, `SVM_RBF`, `SVM_POLY`, `SVM_SIG`, `SVM_OPT`. File `.joblib`
là binary nên không chèn comment trực tiếp; mô tả của chúng nằm ở đây và
trong README.
