from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from ..database import engine, prediction_history, patient_profiles, staff_profiles, staff_patient_assignments
from ..security import current_user, can_access_patient
from ..audit import record

router = APIRouter(prefix="/api/history", tags=["Lịch sử"])


def _history_query(user):
    q = select(prediction_history, patient_profiles.c.patient_code, patient_profiles.c.full_name.label("patient_name"))
    q = q.join(patient_profiles, patient_profiles.c.id == prediction_history.c.patient_id)
    if user["role"] == "patient":
        q = q.where(patient_profiles.c.user_id == user["id"])
    elif user["role"] == "staff":
        with engine.connect() as con:
            staff_id = con.execute(select(staff_profiles.c.id).where(staff_profiles.c.user_id == user["id"])).scalar_one_or_none()
        if not staff_id:
            return q.where(prediction_history.c.id == "__none__")
        q = q.join(staff_patient_assignments, staff_patient_assignments.c.patient_id == patient_profiles.c.id).where(
            staff_patient_assignments.c.staff_id == staff_id,
            staff_patient_assignments.c.status == "active")
    return q.order_by(prediction_history.c.created_at.desc())


@router.get("")
def list_history(limit: int = 100, user=Depends(current_user)):
    limit = max(1, min(limit, 500))
    with engine.connect() as con:
        rows = con.execute(_history_query(user).limit(limit)).mappings().all()
    return {"items": [dict(r) for r in rows], "count": len(rows)}


@router.get("/{record_id}")
def get_history(record_id: str, user=Depends(current_user)):
    with engine.connect() as con:
        row = con.execute(select(prediction_history).where(prediction_history.c.id == record_id)).mappings().first()
    if not row or not can_access_patient(user, row["patient_id"]):
        raise HTTPException(404, "Không tìm thấy lịch sử hoặc bạn không được phân quyền.")
    return dict(row)


@router.delete("/{record_id}")
def delete_history(record_id: str, user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Chỉ Admin được xóa lịch sử dự đoán.")
    with engine.begin() as con:
        row = con.execute(select(prediction_history).where(prediction_history.c.id == record_id)).mappings().first()
        if not row:
            raise HTTPException(404, "Không tìm thấy bản ghi.")
        con.execute(prediction_history.delete().where(prediction_history.c.id == record_id))
    record(user["id"], "prediction_deleted", "prediction", record_id)
    return {"message": "Đã xóa bản ghi."}
