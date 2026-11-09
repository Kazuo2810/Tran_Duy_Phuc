"""Router: admin — các endpoint cùng nhóm chức năng."""
from fastapi import APIRouter
from common import *

router = APIRouter()

@router.get('/api/admin/users', tags=['Quản trị'], summary='Danh sách người dùng')
def admin_users(search: str = Query('', max_length=80), page: int = Query(1, ge=1),
                size: int = Query(20, ge=1, le=100), who=Depends(require_admin)):
    condition = None
    if search.strip():
        pattern = '%' + search.strip() + '%'
        condition = db.users.c.username.ilike(pattern) | db.users.c.name.ilike(pattern)
    query = select(db.users.c.id, db.users.c.username, db.users.c.name,
                   db.users.c.created_at, db.users.c.is_admin)
    count_query = select(func.count()).select_from(db.users)
    if condition is not None:
        query = query.where(condition)
        count_query = count_query.where(condition)
    with db.engine.connect() as con:
        total = con.execute(count_query).scalar_one()
        rows = con.execute(query.order_by(db.users.c.created_at.desc(), db.users.c.id)
                           .offset((page-1)*size).limit(size)).mappings().all()
    return {'items': [dict(row) for row in rows], 'total': total, 'page': page, 'size': size}


@router.get('/api/admin/logs', tags=['Quản trị'], summary='Xem lịch sử toàn hệ thống')
def admin_logs(model: str | None = None, user_id: str | None = None,
               start: date | None = None, end: date | None = None,
               page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
               who=Depends(require_admin)):
    if model:
        check_model(model)
    lower, upper = date_bounds(start, end)
    queries = []
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
    combined = union_all(*queries).subquery()
    with db.engine.connect() as con:
        total = con.execute(select(func.count()).select_from(combined)).scalar_one()
        rows = con.execute(select(combined).order_by(combined.c.time.desc(), combined.c.id)
                           .offset((page-1)*size).limit(size)).mappings().all()
    return {'items': [{**public_log(row),
                       'user_id': row['owner']} for row in rows],
            'total': total, 'page': page, 'size': size}


class AdminLogReference(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: str = Field(min_length=1, max_length=8)
    id: str = Field(min_length=1, max_length=36)


class AdminDeleteLogsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[AdminLogReference] = Field(min_length=1, max_length=100)
    confirm: bool


@router.delete('/api/admin/logs', tags=['Quản trị'], summary='Xóa lịch sử theo quyền quản trị')
def admin_delete_logs(data: AdminDeleteLogsInput, who=Depends(require_admin)):
    if not data.confirm:
        raise HTTPException(400, 'Cần xác nhận xóa lịch sử đã chọn.')
    groups = {}
    for item in data.items:
        check_model(item.model)
        groups.setdefault(item.model, set()).add(item.id)
    # Kiểm tra toàn bộ trước khi xóa; mọi bảng cùng một transaction.
    with db.engine.begin() as con:
        for model, ids in groups.items():
            table = db.logs[model]
            existing = set(con.execute(select(table.c.id).where(table.c.id.in_(ids))).scalars().all())
            if existing != ids:
                raise HTTPException(409, 'Có lịch sử không còn tồn tại. Chưa xóa bản ghi nào; hãy tải lại danh sách.')
        for model, ids in groups.items():
            table = db.logs[model]
            con.execute(delete(table).where(table.c.id.in_(ids)))
    count = sum(len(ids) for ids in groups.values())
    logging.info('Admin %s deleted %s prediction logs', who['id'], count)
    return {'deleted': count, 'message': f'Đã xóa {count} bản ghi lịch sử.'}

