// PHẦN 6 — Xác thực, quản trị và chọn lịch sử. Backend là nơi quyết định quyền thật.
        let irisAuthMode = 'login'; let irisAuthFocus = null;
        // Chuyển đăng nhập/đăng ký; cập nhật trường bắt buộc và xóa mật khẩu cũ.
        function setIrisAuthMode(mode) { irisAuthMode = mode; const reg = mode === 'register'; $('auth-title').textContent = reg ? 'Đăng ký tài khoản' : 'Đăng nhập'; $('auth-submit').textContent = reg ? 'Tạo tài khoản' : 'Đăng nhập'; $('register-name-group').hidden = !reg; $('confirm-password-group').hidden = !reg; $('register-name').required = reg; $('confirm-password').required = reg; $('auth-password').autocomplete = reg ? 'new-password' : 'current-password'; $('auth-switch-text').textContent = reg ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'; $('auth-switch-button').textContent = reg ? 'Đăng nhập' : 'Đăng ký ngay'; $('auth-status').textContent = ''; $('auth-password').value = ''; $('confirm-password').value = ''; }
        // Mở hộp xác thực, nhớ vị trí focus và đưa con trỏ vào tên đăng nhập.
        function openIrisAuth(mode = 'login') { irisAuthFocus = document.activeElement; setIrisAuthMode(mode); $('login-modal').classList.add('active'); $('username-input').focus() }
        // Đóng hộp xác thực, xóa mật khẩu và trả focus về nút đã mở hộp.
        function closeIrisAuth() { $('login-modal').classList.remove('active'); $('auth-password').value = ''; $('confirm-password').value = ''; irisAuthFocus?.focus() }
        // Hiện tên, đăng xuất, sao chép ID hoặc nút đăng nhập/đăng ký; ẩn tab admin.
        function renderIrisAccount() {
            const profile = $('user-profile'); profile.replaceChildren(); $('tab-admin').hidden = !currentAccount?.is_admin;
            if (currentUser) { const name = document.createElement('span'); name.textContent = 'Xin chào, ' + currentUser; const out = document.createElement('button'); out.textContent = 'Đăng xuất'; out.onclick = logout; profile.append(name, out); if (currentAccount?.id) { const copy = document.createElement('button'); copy.textContent = 'ID tài khoản'; copy.title = 'Sao chép ID để cấp quyền quản trị'; copy.onclick = async () => { try { await navigator.clipboard.writeText(currentAccount.id); alert('Đã sao chép ID tài khoản.'); } catch { prompt('ID tài khoản của bạn:', currentAccount.id); } }; profile.append(copy); } }
            else { for (const [label, mode] of [['Đăng nhập', 'login'], ['Đăng ký', 'register']]) { const btn = document.createElement('button'); btn.textContent = label; btn.onclick = () => openIrisAuth(mode); profile.append(btn); } }
        }
        // Xác minh token đã lưu; phục hồi tài khoản hoặc dọn token hết hạn.
        async function restoreIrisSession() {
            if (!token) { renderIrisAccount(); return; }
            const initialToken = token;
            try { const result = await request('/api/auth/me'); if (token !== initialToken) return; currentUser = result.user.name; currentAccount = result.user; renderIrisAccount(); if ($('sec-history').classList.contains('active')) loadLogs(1); }
            catch (error) { if (token !== initialToken) return; if (error.status === 401) { clearIrisSession(); } else { message('history-status', 'Chưa xác minh được phiên đăng nhập: ' + error.message, true); } }
        }
        // Kiểm tra biểu mẫu, gửi đăng ký/đăng nhập và lưu token phiên mới.
        async function submitIrisAuth() {
            const form = $('iris-auth-form'); if (!form.reportValidity()) return;
            const status = $('auth-status'), button = $('auth-submit'); if (button.disabled) return;
            const mode = irisAuthMode; button.disabled = true; $('auth-switch-button').disabled = true; status.textContent = 'Đang xử lý…';
            try {
                const username = $('username-input').value.trim().toLowerCase(), password = $('auth-password').value;
                const payload = { username, password };
                if (mode === 'register') {
                    if (password !== $('confirm-password').value) throw Error('Hai mật khẩu chưa khớp.');
                    payload.name = $('register-name').value.trim(); if (!payload.name) throw Error('Vui lòng nhập họ và tên.');
                }
                const result = await request('/api/auth/' + (mode === 'register' ? 'register' : 'login'), { method: 'POST', body: JSON.stringify(payload) });
                clearIrisSession(); token = result.token; currentUser = result.user.name; currentAccount = result.user; localStorage.setItem('iris_sql_session_token', token);
                renderIrisAccount(); closeIrisAuth(); changeModel(false);
                if ($('sec-history').classList.contains('active')) loadLogs(1);
            } catch (error) { status.textContent = error.message; }
            finally { button.disabled = false; $('auth-switch-button').disabled = false; }
        }
        // Định dạng thời điểm quản trị theo giờ Việt Nam.
        function adminTime(value) { return new Date(value).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }); }
        // Cập nhật trang hiện tại, tổng số bản ghi và nút Trước/Sau.
        function adminPaging(kind, result) { const pages = Math.max(1, Math.ceil(result.total / result.size)); $(kind + '-page').textContent = 'Trang ' + result.page + ' / ' + pages + ' · ' + result.total + ' bản ghi'; $(kind + '-prev').disabled = result.page <= 1; $(kind + '-next').disabled = result.page >= pages; }
        // Quản trị: tìm và phân trang danh sách tài khoản, không nhận phản hồi cũ.
        async function loadAdminUsers(page = 1) {
            if (!currentAccount?.is_admin) return; const version = adminRequestVersion, accountId = currentAccount.id; const call = ++loadAdminUsers.serial;
            message('admin-users-status', 'Đang tải tài khoản…');
            try {
                const params = new URLSearchParams({ page: String(Math.max(1, page)), size: '20', search: $('admin-search').value.trim() }); const result = await request('/api/admin/users?' + params);
                if (version !== adminRequestVersion || currentAccount?.id !== accountId || call !== loadAdminUsers.serial) return;
                adminUserPage = result.page; table('admin-users-table', ['ID tài khoản', 'Tên đăng nhập', 'Họ tên', 'Ngày đăng ký', 'Vai trò'], result.items.map(r => [r.id, r.username, r.name, adminTime(r.created_at), r.is_admin ? 'Quản trị' : 'Người dùng'])); adminPaging('admin-users', result); message('admin-users-status', result.total ? '' : 'Chưa có tài khoản phù hợp.');
            } catch (error) { if (version !== adminRequestVersion || call !== loadAdminUsers.serial) return; message('admin-users-status', error.message, true); $('admin-users-table').replaceChildren(); }
        }
        loadAdminUsers.serial = 0;
        // Quản trị: lọc lịch sử toàn hệ thống theo mô hình, tài khoản và ngày.
        async function loadAdminLogs(page = 1) {
            if (!currentAccount?.is_admin) return; const version = adminRequestVersion, accountId = currentAccount.id; const call = ++loadAdminLogs.serial;
            $('admin-logs-table').replaceChildren(); syncAdminSelection();
            message('admin-logs-status', 'Đang tải lịch sử…');
            try {
                const params = new URLSearchParams({ page: String(Math.max(1, page)), size: '20' }); for (const [key, id] of [['model', 'admin-model'], ['user_id', 'admin-user-id'], ['start', 'admin-start'], ['end', 'admin-end']]) { const value = $(id).value.trim(); if (value) params.set(key, value); }
                const result = await request('/api/admin/logs?' + params); if (version !== adminRequestVersion || currentAccount?.id !== accountId || call !== loadAdminLogs.serial) return;
                adminLogPage = result.page; renderAdminLogs(result.items); adminPaging('admin-logs', result); message('admin-logs-status', result.total ? '' : 'Chưa có lịch sử phù hợp.');
            } catch (error) { if (version !== adminRequestVersion || call !== loadAdminLogs.serial) return; message('admin-logs-status', error.message, true); $('admin-logs-table').replaceChildren(); }
        }
        loadAdminLogs.serial = 0;
        let adminDeleting = false;
        // Đếm dòng quản trị được chọn, cập nhật chọn tất cả và quyền bật nút xóa.
        function syncAdminSelection() {
            const checks = [...document.querySelectorAll('.admin-log-check')], n = checks.filter(c => c.checked).length;
            $('admin-selection-count').textContent = 'Đã chọn ' + n + ' / ' + checks.length + ' bản ghi trên trang';
            $('admin-delete-logs').disabled = adminDeleting || n === 0 || !currentAccount?.is_admin;
            const all = $('admin-select-all'); if (all) { all.checked = checks.length > 0 && n === checks.length; all.indeterminate = n > 0 && n < checks.length; all.disabled = adminDeleting || checks.length === 0; }
        }
        // Dựng lịch sử quản trị cùng checkbox từng dòng và chọn tất cả trên trang.
        function renderAdminLogs(items) {
            table('admin-logs-table', ['Chọn', 'Ngày giờ', 'ID tài khoản / phiên cũ', 'Người thực hiện', 'Mô hình', 'SL / SW / PL / PW (cm)', 'Kết quả', 'Xử lý (ms)'], items.map(r => ['', adminTime(r.time), r.user_id, r.user, r.model, features.map(f => r[f]).join(' / '), r.result, r.elapsed_ms]));
            const all = document.createElement('input'); all.type = 'checkbox'; all.id = 'admin-select-all'; all.setAttribute('aria-label', 'Chọn tất cả lịch sử trên trang');
            all.onchange = () => { document.querySelectorAll('.admin-log-check').forEach(c => c.checked = all.checked); syncAdminSelection(); };
            $('admin-logs-table').querySelector('thead th').replaceChildren(all, document.createTextNode(' Chọn tất cả'));
            $('admin-logs-table').querySelectorAll('tbody tr').forEach((tr, i) => { const c = document.createElement('input'); c.type = 'checkbox'; c.className = 'admin-log-check'; c.dataset.id = items[i].id; c.dataset.model = items[i].model; c.disabled = adminDeleting; c.setAttribute('aria-label', 'Chọn lịch sử ' + items[i].id); c.onchange = syncAdminSelection; tr.cells[0].replaceChildren(c); }); syncAdminSelection();
        }
        // Xác nhận xóa lịch sử toàn hệ thống đã chọn; backend kiểm tra quyền quản trị.
        async function deleteAdminLogs() {
            if (!currentAccount?.is_admin || adminDeleting) return;
            const items = [...document.querySelectorAll('.admin-log-check:checked')].map(c => ({ model: c.dataset.model, id: c.dataset.id }));
            if (!items.length) return;
            if (!confirm(`Xóa vĩnh viễn ${items.length} bản ghi lịch sử đã chọn của người dùng? Không thể hoàn tác.`)) return;
            const version = adminRequestVersion, accountId = currentAccount.id;
            adminDeleting = true; syncAdminSelection(); message('admin-delete-status', 'Đang xóa lịch sử…');
            try {
                const result = await request('/api/admin/logs', { method: 'DELETE', body: JSON.stringify({ items, confirm: true }) });
                if (version !== adminRequestVersion || currentAccount?.id !== accountId) return;
                message('admin-delete-status', result.message); await loadAdminLogs(1); loadLogs(1);
            } catch (error) { if (version === adminRequestVersion && currentAccount?.id === accountId) message('admin-delete-status', error.message, true); }
            finally { adminDeleting = false; syncAdminSelection(); }
        }
        // Lấy checkbox lịch sử cá nhân đang hiển thị và không bị vô hiệu hóa.
        function visibleHistoryChecks() { return [...document.querySelectorAll('#history-tbody input[type=checkbox]')].filter(c => !c.disabled && !c.closest('tr').hidden && c.closest('tr').style.display !== 'none') }
        // Đồng bộ số dòng chọn và trạng thái checkbox chọn tất cả lịch sử cá nhân.
        function syncHistorySelection() { const checks = visibleHistoryChecks(), n = checks.filter(c => c.checked).length; const all = $('select-all-history'); all.checked = checks.length > 0 && n === checks.length; all.indeterminate = n > 0 && n < checks.length; all.disabled = checks.length === 0; $('history-selection-count').textContent = 'Đã chọn ' + n + ' / ' + checks.length + ' bản ghi trên trang' }
        // Khôi phục đăng nhập; gắn submit, chọn tất cả, Escape và vòng focus trong hộp xác thực.
        window.addEventListener('DOMContentLoaded', () => {
            renderIrisAccount();
            restoreIrisSession();
            $('iris-auth-form').addEventListener('submit', e => { e.preventDefault(); submitIrisAuth(); });
            $('select-all-history').addEventListener('change', e => { const selected = e.target.checked; visibleHistoryChecks().forEach(c => { c.checked = selected; c.dispatchEvent(new Event('change', { bubbles: true })) }); syncHistorySelection() }); $('history-tbody').addEventListener('change', syncHistorySelection); new MutationObserver(syncHistorySelection).observe($('history-tbody'), { childList: true, subtree: true }); syncHistorySelection();
            $('login-modal').addEventListener('click', e => { if (e.target.id === 'login-modal') closeIrisAuth() }); document.addEventListener('keydown', e => { const modal = $('login-modal'); if (!modal.classList.contains('active')) return; if (e.key === 'Escape') closeIrisAuth(); if (e.key === 'Tab') { const list = [...modal.querySelectorAll('button,input')].filter(x => !x.disabled && !x.closest('[hidden]')); const first = list[0], last = list.at(-1); if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() } } });
        });
