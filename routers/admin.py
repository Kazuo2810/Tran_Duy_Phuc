"""
Router: admin — Quản lý các chức năng dành riêng cho Quản trị viên (Admin).
Tất cả các endpoint trong file này đều được bảo vệ bởi dependency `require_admin`.
"""
from fastapi import APIRouter
from common import *

router = APIRouter()


@router.get('/api/admin/users', tags=['Quản trị'], summary='Danh sách người dùng')
def admin_users(
    search: str = Query('', max_length=80, description='Từ khóa tìm kiếm theo username hoặc họ tên'),
    page: int = Query(1, ge=1, description='Số trang hiện tại (bắt đầu từ 1)'),
    size: int = Query(20, ge=1, le=100, description='Số lượng bản ghi trên mỗi trang'),
    who=Depends(require_admin)
):
    """
    Lấy danh sách tài khoản người dùng trong hệ thống có hỗ trợ tìm kiếm và phân trang.
    """
    condition = None
    # Nếu có từ khóa tìm kiếm, tạo điều kiện lọc không phân biệt hoa thường (ILIKE)
    if search.strip():
        pattern = '%' + search.strip() + '%'
        condition = db.users.c.username.ilike(pattern) | db.users.c.name.ilike(pattern)

    # Khởi tạo câu truy vấn lấy thông tin cơ bản và câu truy vấn đếm tổng số bản ghi
    query = select(
        db.users.c.id, db.users.c.username, db.users.c.name,
        db.users.c.created_at, db.users.c.is_admin
    )
    count_query = select(func.count()).select_from(db.users)

    # Áp dụng điều kiện lọc vào cả 2 câu truy vấn nếu có
    if condition is not None:
        query = query.where(condition)
        count_query = count_query.where(condition)

    with db.engine.connect() as con:
        total = con.execute(count_query).scalar_one()
        # Sắp xếp người dùng mới nhất lên đầu, sau đó áp dụng phân trang (offset/limit)
        rows = con.execute(
            query.order_by(db.users.c.created_at.desc(), db.users.c.id)
            .offset((page - 1) * size)
            .limit(size)
        ).mappings().all()

    return {
        'items': [dict(row) for row in rows],
        'total': total,
        'page': page,
        'size': size
    }


@router.get('/api/admin/logs', tags=['Quản trị'], summary='Xem lịch sử toàn hệ thống')
def admin_logs(
    model: str | None = None,
    user_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    who=Depends(require_admin)
):
    """
    Truy vấn lịch sử dự đoán trên toàn bộ hệ thống (gộp dữ liệu từ tất cả các bảng log của từng mô hình).
    Hỗ trợ lọc theo tên mô hình, ID người dùng và khoảng thời gian.
    """
    if model:
        check_model(model)
    
    # Chuyển đổi ngày bắt đầu/kết thúc thành mốc thời gian chuẩn (UTC) để so sánh
    lower, upper = date_bounds(start, end)
    queries = []

    # Duyệt qua mô hình được chỉ định hoặc toàn bộ các mô hình trong hệ thống
    for key in ([model] if model else MODEL_NAMES):
        table = db.logs[key]
        query = select(table)
        if user_id:
            query = query.where(table.c.owner == user_id)
        if lower:
            query = query.where(table.c.time >= lower)
        if upper:
            query = query.where(table.c.time < upper)
        queries.append(query)

    # Gộp kết quả từ nhiều bảng bằng UNION ALL và biến thành subquery để đếm & phân trang đồng nhất
    combined = union_all(*queries).subquery()

    with db.engine.connect() as con:
        total = con.execute(select(func.count()).select_from(combined)).scalar_one()
        rows = con.execute(
            select(combined)
            .order_by(combined.c.time.desc(), combined.c.id)
            .offset((page - 1) * size)
            .limit(size)
        ).mappings().all()

    return {
        'items': [{**public_log(row), 'user_id': row['owner']} for row in rows],
        'total': total,
        'page': page,
        'size': size
    }


class AdminLogReference(BaseModel):
    """Schema đại diện cho một bản ghi log cần thao tác (gồm tên model và ID bản ghi)."""
    model_config = ConfigDict(extra='forbid')
    model: str = Field(min_length=1, max_length=8)
    id: str = Field(min_length=1, max_length=36)


class AdminDeleteLogsInput(BaseModel):
    """Schema đầu vào cho yêu cầu xóa hàng loạt log của Admin."""
    model_config = ConfigDict(extra='forbid')
    items: list[AdminLogReference] = Field(min_length=1, max_length=100)
    confirm: bool  # Cờ xác nhận bắt buộc từ phía client để tránh xóa nhầm


@router.delete('/api/admin/logs', tags=['Quản trị'], summary='Xóa lịch sử theo quyền quản trị')
def admin_delete_logs(data: AdminDeleteLogsInput, who=Depends(require_admin)):
    """
    Xóa nhiều bản ghi lịch sử dự đoán trên nhiều bảng mô hình khác nhau.
    Đảm bảo tính toàn vẹn dữ liệu (Atomic Transaction): chỉ xóa khi tất cả bản ghi đều tồn tại.
    """
    if not data.confirm:
        raise HTTPException(400, 'Cần xác nhận xóa lịch sử đã chọn.')

    # Gom nhóm các ID cần xóa theo từng bảng model tương ứng
    groups = {}
    for item in data.items:
        check_model(item.model)
        groups.setdefault(item.model, set()).add(item.id)

    # Mở transaction: kiểm tra sự tồn tại của toàn bộ bản ghi trước khi thực thi lệnh DELETE
    with db.engine.begin() as con:
        for model, ids in groups.items():
            table = db.logs[model]
            existing = set(con.execute(select(table.c.id).where(table.c.id.in_(ids))).scalars().all())
            # Nếu số lượng bản ghi tìm thấy khác với yêu cầu (do đã bị xóa trước đó), hủy toàn bộ thao tác
            if existing != ids:
                raise HTTPException(409, 'Có lịch sử không còn tồn tại. Chưa xóa bản ghi nào; hãy tải lại danh sách.')

        # Thực hiện xóa sau khi đã xác minh 100% bản ghi hợp lệ
        for model, ids in groups.items():
            table = db.logs[model]
            con.execute(delete(table).where(table.c.id.in_(ids)))

    count = sum(len(ids) for ids in groups.values())
    logging.info('Admin %s deleted %s prediction logs', who['id'], count)
    return {'deleted': count, 'message': f'Đã xóa {count} bản ghi lịch sử.'}
