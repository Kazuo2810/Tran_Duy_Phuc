'use strict';
        // PHẦN 4 — Cấu hình API và trạng thái ứng dụng.
        // epoch/logEpoch/visualEpoch chặn phản hồi cũ; token lấy từ phiên SQL của backend.
        // Giao diện được phục vụ cùng FastAPI. Nếu tách host, khai báo window.IRIS_API_BASE trước script này.
        // Thay đổi thành URL thực tế của dịch vụ Auth và dịch vụ Iris của bạn trên Render
        // Cấu hình URL của dịch vụ xác thực độc lập bạn vừa deploy trên Render ở Web Service 1
        const AUTH_API_BASE = 'https://iris-auth-service.onrender.com';

        // URL của ứng dụng Iris chính
        // Để trống nếu HTML được phục vụ cùng FastAPI
        const IRIS_API_BASE = '';

        // Khai báo API_BASE để hàm request() sử dụng
        const API_BASE = IRIS_API_BASE || window.location.origin;

        const $ = id => document.getElementById(id);
        const names = { SVM: 'SVM Linear', SVM_RBF: 'SVM RBF', SVM_POLY: 'SVM Polynomial', SVM_SIG: 'SVM Sigmoid', SVM_OPT: 'SVM RBF tối ưu tham số (GridSearchCV)' };
        const features = ['sepal_length', 'sepal_width', 'petal_length', 'petal_width'];
        const labels = ['Chiều dài đài hoa', 'Chiều rộng đài hoa', 'Chiều dài cánh hoa', 'Chiều rộng cánh hoa'];
        const shortIds = ['sl', 'sw', 'pl', 'pw'];
        const theories = { SVM: 'SVM Linear dùng kernel tuyến tính, C=1 và StandardScaler. Mô hình tìm siêu phẳng phân tách với biên lớn; SVC xử lý bài toán 3 lớp theo chiến lược nhiều bộ phân loại nhị phân.', SVM_RBF: 'SVM RBF dùng kernel Gaussian (RBF), C=1 và gamma=scale để mô hình hóa ranh giới phi tuyến.', SVM_POLY: 'SVM Polynomial dùng kernel đa thức bậc 3, C=1 và gamma=scale để học ranh giới phi tuyến theo tương tác đa thức giữa các đặc trưng.', SVM_SIG: 'SVM Sigmoid dùng kernel sigmoid, C=1 và gamma=scale; kết quả được đánh giá trên cùng tập train/test như các cấu hình còn lại.', SVM_OPT: 'SVM RBF tối ưu tham số bằng GridSearchCV: thử C = 0.1, 1, 10, 100 và gamma = scale, 0.01, 0.1, 1 với cross-validation 5 fold.' };
        const imgs = { setosa: 'https://upload.wikimedia.org/wikipedia/commons/5/56/Kosaciec_szczecinkowaty_Iris_setosa.jpg', versicolor: 'https://upload.wikimedia.org/wikipedia/commons/4/41/Iris_versicolor_3.jpg', virginica: 'https://upload.wikimedia.org/wikipedia/commons/9/9f/Iris_virginica.jpg' };
        const desc = { setosa: 'Iris setosa thường có cánh hoa ngắn và hẹp trong tập Iris. Mô hình phân loại bằng số đo, không phân tích ảnh.', versicolor: 'Iris versicolor thường có kích thước cánh hoa trung gian; một số mẫu gần với Virginica.', virginica: 'Iris virginica thường có cánh hoa dài và rộng hơn hai nhóm còn lại trong tập dữ liệu.' };
        let currentUser = '';
        let currentAccount = null;
        let adminUserPage = 1, adminLogPage = 1, adminRequestVersion = 0;
        let token = localStorage.getItem('iris_sql_session_token') || '';
        let currentModel = location.pathname.split('/')[2] || 'SVM';
        if (!names[currentModel]) currentModel = 'SVM';
        let epoch = 0, report = null, dataset = null, prediction = null, logPage = 1, logTotal = 0, visibleLogs = [];
        let logEpoch = 0, visualEpoch = 0;
        let apiControllers = new Set();
        let objectUrls = {};
        const modelForms = {};
        // Gọi API: gắn token, chờ tối đa 45 giây, đọc JSON hoặc Blob và chuẩn hóa lỗi.
        async function request(path, options = {}) {
            const controller = new AbortController(); apiControllers.add(controller);
            const timeout = setTimeout(() => controller.abort(), 45000);
            const { binary = false, ...rest } = options;
            try {
                const response = await fetch(API_BASE + path, { ...rest, signal: controller.signal, headers: { ...(token ? { 'X-Session-Token': token } : {}), ...(rest.body ? { 'Content-Type': 'application/json' } : {}), ...rest.headers } });
                if (!response.ok) {
                    let message = `Yêu cầu thất bại (HTTP ${response.status}).`;
                    try { const data = await response.json(); message = typeof data.detail === 'string' ? data.detail : message; } catch { }
                    const error = new Error(message); error.status = response.status; throw error;
                }
                return binary ? await response.blob() : await response.json();
            } catch (error) {
                if (error.name === 'AbortError') throw new Error('Yêu cầu đã bị hủy hoặc quá thời gian chờ.');
                throw error;
            } finally { clearTimeout(timeout); apiControllers.delete(controller); }
        }
        // Hủy các yêu cầu đang chạy khi đổi mô hình hoặc tài khoản.
        function cancelRequests() { for (const c of apiControllers) c.abort(); apiControllers.clear(); }
        // Hiện thông báo bằng textContent và bật màu lỗi khi cần.
        function message(id, text, error = false) { $(id).textContent = text; $(id).classList.toggle('error', error); }
        // Định dạng tỷ lệ 0–1 thành phần trăm; giá trị thiếu hiện N/A.
        function pct(value) { return Number.isFinite(value) ? (value * 100).toFixed(2) + '%' : 'N/A'; }
        // Dựng bảng từ tiêu đề và dữ liệu; dùng textContent để tránh chèn HTML.
        function table(target, headers, rows) {
            const t = document.createElement('table'), head = document.createElement('thead'), hr = document.createElement('tr');
            headers.forEach(x => { const th = document.createElement('th'); th.textContent = x; hr.append(th); }); head.append(hr); t.append(head);
            const body = document.createElement('tbody'); rows.forEach(row => { const tr = document.createElement('tr'); row.forEach(value => { const td = document.createElement('td'); td.textContent = value ?? '—'; tr.append(td); }); body.append(tr); }); t.append(body); $(target).replaceChildren(t);
        }
        // Cập nhật khu vực tài khoản trên thanh điều hướng.
        function updateProfileUI() { renderIrisAccount(); }
        // Mở hộp đăng nhập khi chức năng yêu cầu xác thực.
        function showLoginModal() { openIrisAuth('login'); }
        // Đóng hộp xác thực qua hàm dùng chung.
        function closeLoginModal() { closeIrisAuth(); }
        // Nhấn Enter để gửi biểu mẫu xác thực với kiểm tra hợp lệ.
        function handleLoginKey(e) { if (e.key === 'Enter') { e.preventDefault(); $('iris-auth-form').requestSubmit(); } }
        // Giữ tên hàm tương thích; chuyển xử lý sang submitIrisAuth.
        async function login() { return submitIrisAuth(); }
        // Xóa phiên cục bộ, hủy yêu cầu cũ và dọn dữ liệu riêng của tài khoản.
        function clearIrisSession() {
            epoch++; logEpoch++; adminRequestVersion++; cancelRequests(); currentUser = ''; currentAccount = null; token = '';
            $('admin-users-table').replaceChildren(); $('admin-logs-table').replaceChildren(); syncAdminSelection(); message('admin-delete-status', '');
            if ($('sec-admin').classList.contains('active')) switchTab('intro');
            localStorage.removeItem('iris_sql_session_token');
            resetBatchResult();
            resetResult(); visibleLogs = []; logPage = 1; logTotal = 0;
            $('history-tbody').replaceChildren();
            message('history-status', 'Đăng nhập để xem lịch sử của tài khoản.');
            $('spinner').style.display = 'none'; $('btn-submit').disabled = false;
            $('btn-submit').textContent = 'Dự đoán & Lưu Log'; renderIrisAccount();
        }
        // Đăng xuất ở backend rồi dọn phiên trình duyệt; giữ thông báo nếu lỗi.
        async function logout() {
            try { await request('/api/auth/logout', { method: 'POST' }); clearIrisSession(); }
            catch (error) { alert('Chưa đăng xuất được: ' + error.message); }
        }
        // Đổi sáng/tối, lưu lựa chọn và vẽ lại biểu đồ theo màu giao diện.
        function toggleTheme() {
            const dark = document.body.dataset.theme !== 'dark'; document.body.dataset.theme = dark ? 'dark' : 'light';
            localStorage.setItem('iris_theme', dark ? 'dark' : 'light'); $('theme-btn').textContent = dark ? '☀️' : '🌙'; drawData();
        }
        // Chuyển trang; chặn trang quản trị ở UI và tải dữ liệu tương ứng.
        function switchTab(id) {
            if (id === 'admin' && !currentAccount?.is_admin) { alert('Chỉ tài khoản quản trị được truy cập.'); return; }
            if (id === 'admin') { loadAdminUsers(1); loadAdminLogs(1); }
            document.querySelectorAll('section').forEach(s => s.classList.toggle('active', s.id === 'sec-' + id));
            document.querySelectorAll('.nav-links a').forEach(a => a.classList.toggle('active', a.id === 'tab-' + id));
            if (id === 'history') loadLogs(1); if (id === 'data') drawData(); if (id === 'visual') loadVisual();
            if (id === 'compare') loadComparison();
        }
        // Ghi nhớ bốn số đo riêng cho mô hình hiện tại.
        function rememberForm() { modelForms[currentModel] = shortIds.map(id => $(id + '_input').value); }
        // Dọn kết quả dự đoán đơn và thông báo liên quan.
        function resetResult() { prediction = null; $('res-container').style.display = 'none'; $('res-placeholder').style.display = 'block'; message('prediction-error', ''); message('save-status', ''); }
        // Đổi mô hình, khôi phục số đo, cập nhật URL và tải lại báo cáo/lịch sử.
        function changeModel(push = true) {
            rememberForm(); currentModel = $('global-model-selector').value;
            epoch++; logEpoch++; visualEpoch++; cancelRequests(); report = null; resetResult();
            $('spinner').style.display = 'none'; $('btn-submit').disabled = false; $('btn-submit').textContent = 'Dự đoán & Lưu Log';
            if (push) history.pushState({}, '', `/models/${currentModel}`);
            const values = modelForms[currentModel] || [5.1, 3.5, 1.4, .2]; fillSample(...values);
            resetBatchResult(); $('batch-model-name').textContent = currentModel;
            $('current-model-badge').textContent = 'Đang dùng: ' + currentModel; $('intro-model').textContent = names[currentModel]; $('intro-theory').textContent = theories[currentModel];
            $('eval-model-name').value = currentModel; $('filter-model').value = '';
            $('filter-start').value = ''; $('filter-end').value = ''; $('filter-user').value = '';
            $('metrics').replaceChildren(); $('confusion').replaceChildren(); $('class-report').replaceChildren(); message('eval-note', ''); message('eval-details', '');
            $('history-tbody').replaceChildren(); visibleLogs = []; message('history-status', '');
            ['decision-img', 'extra-img'].forEach(id => { $(id).style.display = 'none'; $(id).removeAttribute('src'); }); message('importance', '');
            loadEvaluation(); loadLogs(1); if (!dataset) loadData();
            if ($('sec-visual').classList.contains('active')) loadVisual();
        }
        // Tải báo cáo: Accuracy, Precision, Recall, F1, CV, ma trận và tham số.
        async function loadEvaluation() {
            const e = epoch, m = currentModel; message('eval-status', 'Đang tải báo cáo…');
            try {
                const data = await request(`/api/models/${m}/evaluate`); if (e !== epoch) return; report = data;
                const metrics = [['Accuracy test', data.test_accuracy], ['Precision macro', data.precision], ['Recall macro', data.recall], ['F1 macro', data.f1], ['CV train', data.cv_accuracy], ['Độ lệch chuẩn CV', data.cv_std]];
                $('metrics').replaceChildren(); for (const [label, value] of metrics) { const div = document.createElement('div'); div.className = 'stat'; const strong = document.createElement('strong'); strong.textContent = pct(value); div.append(document.createTextNode(label), strong); $('metrics').append(div); }
                message('eval-status', `Phiên bản ${data.version} · Train ${data.train_count} / Test ${data.test_count} · Triển khai ${data.deployment_count} mẫu`);
                message('eval-note', data.deployment_note + ' ' + data.cv_scope);
                table('confusion', ['Thật / Dự đoán', 'Setosa', 'Versicolor', 'Virginica'], data.confusion_matrix.map((r, i) => [['Setosa', 'Versicolor', 'Virginica'][i], ...r]));
                const cr = data.classification_report;
                table('class-report', ['Lớp / Trung bình', 'Precision', 'Recall', 'F1', 'Số mẫu'], ['setosa', 'versicolor', 'virginica', 'macro avg', 'weighted avg'].map(k => [k, pct(cr[k].precision), pct(cr[k].recall), pct(cr[k]['f1-score']), cr[k].support]));
                message('eval-details', JSON.stringify({ parameters: data.parameters, cv_scores: data.cv_scores, metric_scale: data.metric_scale, random_state: data.random_state, sklearn: data.sklearn_version }, null, 2));
            } catch (error) { if (e === epoch) message('eval-status', error.message, true); }
        }
        // Nạp bốn số đo vào ô nhập và đồng bộ thanh trượt.
        function fillSample(...values) { shortIds.forEach((id, i) => { const n = $(id + '_input'), r = $(id + '_range'); n.value = values[i]; syncRange(r, n.value); }); }
        // Mở rộng giới hạn thanh trượt khi số nhập hợp lệ vượt phạm vi mặc định.
        function syncRange(range, value) { const v = Number(value); if (Number.isFinite(v) && v > 0) { range.min = Math.min(Number(range.dataset.min), v); range.max = Math.max(Number(range.dataset.max), v); range.value = v; } }
        // Trả về mẫu mặc định và xóa kết quả dự đoán đơn.
        function resetForm() { fillSample(5.1, 3.5, 1.4, .2); resetResult(); }
        let batchResult = null;
        // Xóa bảng kết quả hàng loạt và khóa nút tải kết quả cũ.
        function resetBatchResult() { batchResult = null; $('batch-results').replaceChildren(); $('batch-download').disabled = true; message('batch-status', ''); }
        // Đọc CSV/XLSX/JSON dưới 5 MB, gửi Base64 và hiển thị dự đoán từng dòng.
        async function submitBatchPrediction() {
            if (!currentUser) { showLoginModal(); return; }
            const file = $('batch-file').files[0], button = $('batch-submit');
            if (button.disabled) return;
            if (!file) { message('batch-status', 'Hãy chọn file cần dự đoán.', true); return; }
            if (!/\.(csv|xlsx|json)$/i.test(file.name) || file.size > 5 * 1024 * 1024) { message('batch-status', 'Chọn file .csv, .xlsx hoặc .json, tối đa 5 MB.', true); return; }
            const e = epoch, m = currentModel; resetBatchResult(); button.disabled = true; $('batch-file').disabled = true;
            message('batch-status', 'Đang đọc file và dự đoán bằng ' + m + '…');
            try {
                const encoded = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.onerror = () => reject(new Error('Không đọc được file.')); reader.readAsDataURL(file); });
                if (e !== epoch) return;
                const result = await request(`/api/models/${m}/predict-batch`, { method: 'POST', body: JSON.stringify({ filename: file.name, content_base64: encoded }) });
                if (e !== epoch) return;
                batchResult = result; $('batch-download').disabled = false;
                table('batch-results', ['Dòng trong file', 'SL / SW / PL / PW (cm)', 'Loài dự đoán', 'Mô hình', 'Lưu SQL'], result.items.map(r => [r.source_row, features.map(f => r[f]).join(' / '), r.result, r.model, result.saved ? 'Đã lưu' : 'Chưa lưu']));
                message('batch-status', `Đã dự đoán ${result.count} mẫu bằng ${result.model} trong ${result.elapsed_ms} ms. ${result.message}`, !result.saved);
                loadLogs(1);
            } catch (error) { if (e === epoch) message('batch-status', error.message, true); }
            finally { button.disabled = false; $('batch-file').disabled = false; }
        }
        // Xuất lô vừa dự đoán thành CSV UTF-8 BOM, có nhãn và trạng thái SQL.
        function downloadBatchResults() {
            if (!batchResult) return;
            const headers = ['source_row', ...features, 'prediction', 'model', 'version', 'time', 'saved_sql'];
            const quote = v => '"' + String(v ?? '').replaceAll('"', '""') + '"';
            const rows = batchResult.items.map(r => [r.source_row, ...features.map(f => r[f]), r.result, r.model, r.version, r.time, batchResult.saved]);
            const csv = '\uFEFF' + [headers, ...rows].map(r => r.map(quote).join(',')).join('\r\n');
            download(new Blob([csv], { type: 'text/csv;charset=utf-8' }), 'Iris_du_doan_hang_loat.csv');
        }
        // Kiểm tra bốn số dương; dự đoán đơn, ảnh loài, cảnh báo và trạng thái lưu.
        async function submitPrediction() {
            if (!currentUser) { showLoginModal(); return; }
            const values = shortIds.map(id => Number($(id + '_input').value));
            if (values.some(v => !Number.isFinite(v) || v <= 0)) { message('prediction-error', 'Hãy nhập đủ 4 số đo hữu hạn, lớn hơn 0.', true); return; }
            const payload = Object.fromEntries(features.map((f, i) => [f, values[i]])), e = epoch, m = currentModel;
            resetResult(); $('res-placeholder').style.display = 'none'; $('spinner').style.display = 'block'; $('btn-submit').disabled = true; $('btn-submit').textContent = 'Đang xử lý…';
            try {
                const data = await request(`/api/models/${m}/predict`, { method: 'POST', body: JSON.stringify(payload) }); if (e !== epoch) return;
                if (data.model !== m) throw new Error('Model trả về không khớp yêu cầu.');
                const species = String(data.prediction).toLowerCase().replace(/^iris[\s_-]*/, ''); if (!desc[species]) throw new Error('API trả về tên loài không hợp lệ.');
                prediction = data; $('res-name').textContent = 'Iris ' + species; $('flower-desc').textContent = desc[species];
                $('res-img').style.display = 'block'; $('res-img').src = document.querySelectorAll('.species-pick img')[['setosa', 'versicolor', 'virginica'].indexOf(species)]?.src || imgs[species]; $('img-wrapper').style.display = 'block'; message('image-note', '');
                message('save-status', data.message, !data.saved); $('save-status').classList.toggle('ok', data.saved);
                message('prediction-meta', `${data.model} · phiên bản ${data.version} · ${data.elapsed_ms} ms`);
                message('prediction-warning', data.warnings.join(' ') || 'Số đo nằm trong phạm vi từng đặc trưng của tập train.');
                const { export_token, ...publicData } = data; message('response-json', JSON.stringify(publicData, null, 2)); $('res-container').style.display = 'flex';
                if (data.saved) loadLogs(1);
            } catch (error) { if (e === epoch) { message('prediction-error', error.message, true); $('res-placeholder').style.display = 'block'; } }
            finally { if (e === epoch) { $('spinner').style.display = 'none'; $('btn-submit').disabled = false; $('btn-submit').textContent = 'Dự đoán & Lưu Log'; } }
        }
        // Tạo bộ lọc lịch sử; kiểm tra ngày bắt đầu không sau ngày kết thúc.
        function filters(all = false) {
            const q = new URLSearchParams(); if (all) return q;
            const map = { 'filter-model': 'model', 'filter-user': 'user', 'filter-start': 'start', 'filter-end': 'end' };
            for (const [id, key] of Object.entries(map)) { const value = $(id).value.trim(); if (value) q.set(key, value); }
            if (q.get('start') && q.get('end') && q.get('start') > q.get('end')) throw new Error('Ngày bắt đầu phải không sau ngày kết thúc.');
            return q;
        }
        // Bỏ bộ lọc và tải lại trang đầu của lịch sử cá nhân.
        function resetFilters() { $('filter-model').value = '';['filter-user', 'filter-start', 'filter-end'].forEach(id => $(id).value = ''); loadLogs(1); }
        // Tải lịch sử cá nhân có phân trang, checkbox và chặn phản hồi đã cũ.
        async function loadLogs(page = 1) {
            const e = epoch, le = ++logEpoch; visibleLogs = []; $('history-tbody').replaceChildren(); $('delete-logs').disabled = true;
            if (!currentUser) { message('history-status', 'Đăng nhập để xem lịch sử của tài khoản.'); return; }
            message('history-status', 'Đang tải lịch sử SQL…');
            try {
                const q = filters(); q.set('page', Math.max(1, page)); q.set('size', 20);
                const data = await request('/api/logs?' + q); if (e !== epoch || le !== logEpoch) return;
                visibleLogs = data.items; logPage = data.page; logTotal = data.total;
                for (const log of visibleLogs) {
                    const tr = document.createElement('tr'), td = document.createElement('td'), cb = document.createElement('input'); cb.type = 'checkbox'; cb.value = log.id; cb.dataset.model = log.model; cb.setAttribute('aria-label', 'Chọn log ' + log.id); td.append(cb); tr.append(td);
                    const cells = [log.id, new Date(log.time).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }), log.user, log.model + ' / ' + log.version, features.map(f => log[f]).join(', '), log.result];
                    cells.forEach(v => { const cell = document.createElement('td'); cell.textContent = v; tr.append(cell); }); $('history-tbody').append(tr);
                }
                message('history-status', data.total ? `${data.total} bản ghi phù hợp.` : 'Không có bản ghi phù hợp.');
                $('page-info').textContent = `Trang ${logPage} / ${Math.max(1, Math.ceil(logTotal / 20))}`;
                $('prev-page').disabled = logPage <= 1; $('next-page').disabled = logPage * 20 >= logTotal; $('delete-logs').disabled = !visibleLogs.length;
            } catch (error) { if (e === epoch && le === logEpoch) message('history-status', error.message, true); }
        }
        // Xác nhận rồi xóa các dòng đã chọn theo từng mô hình; báo lỗi từng nhóm.
        async function clearHistory() {
            const checked = [...$('history-tbody').querySelectorAll('input[type="checkbox"]:checked')];
            if (!checked.length) { alert('Chọn các bản ghi muốn xóa trên trang hiện tại.'); return; }
            const groups = new Map();
            for (const c of checked) { const model = c.dataset.model; if (!names[model]) { message('history-status', 'Bản ghi có mã mô hình không hợp lệ. Hãy tải lại lịch sử.', true); return; } if (!groups.has(model)) groups.set(model, []); groups.get(model).push(c.value); }
            if (!confirm(`Xóa ${checked.length} bản ghi đã chọn của ${[...groups.keys()].join(', ')}?`)) return;
            const e = epoch; let deleted = 0; const failures = []; $('delete-logs').disabled = true;
            try {
                for (const [model, ids] of groups) { if (e !== epoch) return; try { const data = await request(`/api/models/${encodeURIComponent(model)}/logs`, { method: 'DELETE', body: JSON.stringify({ ids, confirm: true }) }); deleted += data.deleted; } catch (error) { failures.push(model + ': ' + error.message); } }
                if (e !== epoch) return; await loadLogs(1); if (e !== epoch) return; message('history-status', `Đã xóa ${deleted} bản ghi.` + (failures.length ? ' Chưa xóa được: ' + failures.join(' · ') : ''), failures.length > 0);
            } finally { if (e === epoch) $('delete-logs').disabled = !visibleLogs.length; }
        }
        // Tải Blob bằng liên kết tạm và thu hồi URL sau khi sử dụng.
        function download(blob, name) { const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 5000); }
        // Xuất lịch sử Excel theo bộ lọc hoặc toàn bộ lịch sử tài khoản.
        async function exportToExcel(all = false) {
            if (!currentUser) { showLoginModal(); return; }
            try { download(await request('/api/export?' + filters(all), { binary: true }), all ? 'Iris_tat_ca.xlsx' : 'Iris_theo_bo_loc.xlsx'); }
            catch (error) { message('history-status', error.message, true); }
        }
        // Xuất kết quả đơn bằng phiếu có chữ ký do backend cấp.
        async function exportCurrent() {
            if (!prediction) return;
            try { download(await request('/api/export-current', { method: 'POST', body: JSON.stringify({ token: prediction.export_token }), binary: true }), 'Iris_ket_qua_hien_tai.xlsx'); }
            catch (error) { message('prediction-error', error.message, true); }
        }
        // Hiện bảng so sánh năm cấu hình SVM từ các báo cáo huấn luyện.
        async function loadComparison() {
            message('compare-status', 'Đang tải báo cáo…');
            try { const rows = await request('/api/models'); table('comparison', ['Model', 'Phiên bản', 'Test Accuracy', 'Precision macro', 'Recall macro', 'F1 macro', 'CV ± SD'], rows.map(x => x.report ? [names[x.model], x.report.version, pct(x.report.test_accuracy), pct(x.report.precision), pct(x.report.recall), pct(x.report.f1), pct(x.report.cv_accuracy) + ' ± ' + pct(x.report.cv_std)] : [names[x.model], 'Chưa huấn luyện', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'])); message('compare-status', ''); }
            catch (error) { $('comparison').replaceChildren(); message('compare-status', error.message, true); }
        }
        // Tải ảnh biểu đồ, thay URL cũ và bỏ qua phản hồi của mô hình trước.
        async function setPlot(id, path, e, ve) {
            const blob = await request(path, { binary: true }); if (e !== epoch || ve !== visualEpoch) return;
            if (objectUrls[id]) URL.revokeObjectURL(objectUrls[id]); objectUrls[id] = URL.createObjectURL(blob); $(id).src = objectUrls[id]; $(id).style.display = 'block';
        }
        // Vẽ lát cắt ranh giới của cấu hình SVM đang chọn; đánh dấu support vectors nếu có.
        async function loadVisual() {
            const e = epoch, ve = ++visualEpoch, m = currentModel, x = Number($('visual-x').value), y = Number($('visual-y').value);
            ['decision-img', 'extra-img'].forEach(id => $(id).style.display = 'none'); message('importance', '');
            if (x === y) { message('visual-status', 'Hãy chọn hai đặc trưng khác nhau.', true); return; }
            message('visual-status', 'Đang tạo biểu đồ từ mô hình…');
            try {
                await setPlot('decision-img', `/api/models/${m}/visual/decision?x=${x}&y=${y}`, e, ve);
                if (e !== epoch || ve !== visualEpoch) return;
                if (m === 'SVM') await setPlot('extra-img', `/api/models/${m}/visual/margin`, e, ve);
                if (e === epoch && ve === visualEpoch) message('visual-status', 'Biểu đồ là lát cắt của cấu hình SVM triển khai trên 4 đặc trưng; các support vectors được đánh dấu nếu mô hình cung cấp.');
            } catch (error) { if (e === epoch && ve === visualEpoch) message('visual-status', error.message, true); }
        }
        // Khởi tạo canvas với kích thước và màu chữ thống nhất.
        function canvas(id) { const c = $(id); c.style.width = '100%'; c.style.height = '300px'; c.width = 600; c.height = 400; const ctx = c.getContext('2d'); ctx.clearRect(0, 0, 600, 400); ctx.font = '16px Inter, sans-serif'; ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--text-main'); return ctx; }
        // Vẽ biểu đồ số mẫu theo loài và scatter theo hai đặc trưng khác nhau.
        function drawData() {
            if (!dataset) return;
            const colors = ['#0ea5e9', '#f59e0b', '#8b5cf6']; const counts = dataset.classes.map((_, i) => dataset.target.filter(t => t === i).length);
            const b = canvas('barChart'); b.fillText('Số mẫu theo loài (tổng 150)', 70, 30);
            counts.forEach((n, i) => { b.fillStyle = colors[i]; b.fillRect(90 + i * 160, 330 - n * 4, 70, n * 4); b.fillText(String(n), 110 + i * 160, 315 - n * 4); b.fillText(dataset.classes[i], 75 + i * 160, 365); });
            const x = Number($('data-x').value), y = Number($('data-y').value);
            if (x === y) { message('data-status', 'Hãy chọn hai đặc trưng khác nhau.', true); return; } message('data-status', '150 mẫu, không thiếu dữ liệu.');
            const c = canvas('scatterChart'), minx = dataset.min[x] - .2, maxx = dataset.max[x] + .2, miny = dataset.min[y] - .2, maxy = dataset.max[y] + .2;
            c.fillText(labels[x] + ' (cm)', 130, 390); c.fillText(labels[y] + ' (cm)', 60, 24); c.strokeStyle = '#94a3b8'; c.beginPath(); c.moveTo(60, 45); c.lineTo(60, 340); c.lineTo(570, 340); c.stroke();
            for (let i = 0; i <= 5; i++) { const vx = minx + (maxx - minx) * i / 5, vy = miny + (maxy - miny) * i / 5; c.fillText(vx.toFixed(1), 50 + i * 100, 365); c.fillText(vy.toFixed(1), 16, 345 - i * 56); }
            dataset.data.forEach((r, i) => { c.fillStyle = colors[dataset.target[i]]; c.beginPath(); c.arc(60 + (r[x] - minx) / (maxx - minx) * 500, 340 - (r[y] - miny) / (maxy - miny) * 280, 4, 0, Math.PI * 2); c.fill(); });
        }
        // Tải CSV 150 mẫu Iris; khóa nút trong lúc chờ và hiển thị kết quả tải.
        async function downloadSampleData() {
            const button = $('download-sample-btn');
            if (button.disabled) return;
            button.disabled = true; message('sample-download-status', 'Đang tải dữ liệu mẫu…');
            try {
                const blob = await request('/api/data/sample.csv', { binary: true });
                download(blob, 'iris_du_lieu_mau.csv');
                message('sample-download-status', 'Đã tải file gồm 150 mẫu Iris.');
            } catch (error) { message('sample-download-status', 'Không tải được dữ liệu mẫu: ' + error.message, true); }
            finally { button.disabled = false; }
        }
        // Đọc bộ Iris từ API rồi vẽ các biểu đồ khám phá dữ liệu.
        async function loadData() { try { dataset = await request('/api/data'); drawData(); } catch (e) { message('data-status', e.message, true); } }
        // Kiểm tra API, SQL và số mô hình sẵn sàng qua /health.
        async function health() { try { const data = await request('/health'); message('system-status', `● API & SQL sẵn sàng · ${data.models.length}/5 model`); } catch (e) { message('system-status', '● Hệ thống chưa sẵn sàng: ' + e.message, true); } }
        // Khởi tạo số đo, bộ chọn trục, giao diện, mô hình, sức khỏe API và điều hướng bàn phím.
        window.addEventListener('DOMContentLoaded', () => {
            shortIds.forEach(id => { const range = $(id + '_range'), num = $(id + '_input'); range.dataset.min = range.min; range.dataset.max = range.max; num.min = '0.000001'; range.addEventListener('input', () => num.value = range.value); num.addEventListener('input', () => syncRange(range, num.value)); });
            ['data-x', 'data-y', 'visual-x', 'visual-y'].forEach(id => labels.forEach((text, i) => { const option = document.createElement('option'); option.value = i; option.textContent = text; $(id).append(option); }));
            $('data-x').value = $('visual-x').value = 2; $('data-y').value = $('visual-y').value = 3;
            document.body.dataset.theme = localStorage.getItem('iris_theme') || 'light'; $('theme-btn').textContent = document.body.dataset.theme === 'dark' ? '☀️' : '🌙';
            $('global-model-selector').value = currentModel; updateProfileUI(); changeModel(false); health();
            document.querySelectorAll('.nav-links a[tabindex]').forEach(a => a.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); a.click(); } }));
            if (location.pathname === '/compare') switchTab('compare');
        });
        // Đồng bộ mô hình/trang khi người dùng bấm Back hoặc Forward của trình duyệt.
        window.addEventListener('popstate', () => { const model = location.pathname.split('/')[2]; if (names[model]) { $('global-model-selector').value = model; changeModel(false); } if (location.pathname === '/compare') switchTab('compare'); });
