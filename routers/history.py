"""
Router: history — Quản lý (xem và xóa) lịch sử dự đoán cá nhân của người dùng đang đăng nhập.
"""
from fastapi import APIRouter
from common import *

router = APIRouter()


@router.get('/api/logs', tags=['Lịch sử'], summary='Lịch sử cá nhân — tất cả hoặc lọc theo mô hình')
def get_logs(
    model: str | None = None,
    user: str | None = None,
    start: date | None = None,
    end: date | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    who=Depends(session)
):
    """Lấy danh sách lịch sử dự đoán của chính người dùng hiện tại, có phân trang và lọc."""
    rows = query_rows(who['owner'], model, user, start, end)
    return {
        'items': rows[(page - 1) * size : page * size],
        'total': len(rows),
        'page': page,
        'size': size
    }


@router.get('/api/models/{model}/logs', tags=['Lịch sử'], summary='Lịch sử cá nhân — một mô hình')
def model_logs(
    model: str,
    user: str | None = None,
    start: date | None = None,
    end: date | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    who=Depends(session)
):
    """Lấy lịch sử dự đoán cá nhân dành riêng cho một mô hình cụ thể."""
    check_model(model)
    return get_logs(model, user, start, end, page, size, who)


class DeleteInput(BaseModel):
    """Schema danh sách các ID bản ghi cần xóa và cờ xác nhận."""
    ids: list[str] = Field(min_length=1, max_length=100)
    confirm: bool


@router.delete('/api/models/{model}/logs', tags=['Lịch sử'], summary='Xóa lịch sử cá nhân theo mô hình')
def delete_logs(model: str, data: DeleteInput, who=Depends(session)):
    """
    Xóa các bản ghi lịch sử thuộc về người dùng hiện tại trong bảng của mô hình chỉ định.
    Kiểm tra quyền sở hữu (`owner == who['owner']`) để ngăn người dùng xóa dữ liệu của người khác.
    """
    check_model(model)
    if not data.confirm:
        raise HTTPException(400, 'Cần xác nhận xóa các ID đã chọn.')

    table = db.logs[model]
    with db.engine.begin() as con:
        # Kiểm tra tất cả ID gửi lên đều tồn tại và thuộc quyền sở hữu của user hiện tại
        matched = con.execute(
            select(table.c.id).where(table.c.owner == who['owner'], table.c.id.in_(data.ids))
        ).scalars().all()

        if set(matched) != set(data.ids):
            raise HTTPException(409, 'Có log không tồn tại hoặc không thuộc tài khoản/model này; chưa xóa bản ghi nào.')

        con.execute(delete(table).where(table.c.id.in_(data.ids)))

    return {'deleted': len(matched), 'ids': matched}
