import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, insert, update, and_
from ..database import engine, patient_profiles, staff_profiles, staff_patient_assignments, app_users, patient_records
from ..schemas import PatientCreate, PatientUpdate, RecordCreate
from ..security import current_user, require_roles, can_access_patient
from ..audit import record

router = APIRouter(prefix="/api", tags=["Hồ sơ bệnh nhân"])


def _public(row, user):
    data = dict(row)
    if user["role"] == "patient":
        data.pop("notes", None)
    return data


def _patient_rows_for(user):
    with engine.connect() as con:
        if user["role"] == "admin":
            rows = con.execute(select(patient_profiles).order_by(patient_profiles.c.created_at.desc())).mappings().all()
        elif user["role"] == "patient":
            rows = con.execute(select(patient_profiles).where(patient_profiles.c.user_id == user["id"])).mappings().all()
        else:
            staff_id = con.execute(select(staff_profiles.c.id).where(staff_profiles.c.user_id == user["id"])).scalar_one_or_none()
            if not staff_id:
                return []
            q = select(patient_profiles).join(staff_patient_assignments,
                staff_patient_assignments.c.patient_id == patient_profiles.c.id).where(
                staff_patient_assignments.c.staff_id == staff_id,
                staff_patient_assignments.c.status == "active").order_by(patient_profiles.c.created_at.desc())
            rows = con.execute(q).mappings().all()
    return [_public(row, user) for row in rows]


@router.get("/patients")
def list_patients(user=Depends(current_user)):
    rows = _patient_rows_for(user)
    return {"items": rows, "count": len(rows)}


@router.post("/patients", status_code=201)
def create_patient(payload: PatientCreate, user=Depends(require_roles("admin", "staff"))):
    patient_id = str(uuid.uuid4())
    code = payload.patient_code or "P-" + uuid.uuid4().hex[:8].upper()
    if payload.user_id:
        with engine.connect() as con:
            account = con.execute(select(app_users).where(app_users.c.id == payload.user_id)).mappings().first()
        if not account or account["role"] != "patient":
            raise HTTPException(422, "user_id phải là tài khoản có vai trò patient trong Healthcare.")
    values = payload.model_dump()
    values.update(id=patient_id, patient_code=code, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    try:
        with engine.begin() as con:
            con.execute(insert(patient_profiles).values(**values))
            if user["role"] == "staff":
                staff_id = con.execute(select(staff_profiles.c.id).where(staff_profiles.c.user_id == user["id"])).scalar_one_or_none()
                if not staff_id:
                    raise HTTPException(403, "Tài khoản chưa có hồ sơ nhân viên.")
                con.execute(insert(staff_patient_assignments).values(
                    id=str(uuid.uuid4()), staff_id=staff_id, patient_id=patient_id,
                    assigned_by=user["id"], status="active", assigned_at=datetime.now(timezone.utc)))
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(409, "Không thể tạo hồ sơ. Mã bệnh nhân hoặc tài khoản có thể đã tồn tại.")
    record(user["id"], "patient_created", "patient", patient_id)
    with engine.connect() as con:
        row = con.execute(select(patient_profiles).where(patient_profiles.c.id == patient_id)).mappings().one()
    return _public(row, user)


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str, user=Depends(current_user)):
    if not can_access_patient(user, patient_id):
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc bạn không được phân quyền.")
    with engine.connect() as con:
        row = con.execute(select(patient_profiles).where(patient_profiles.c.id == patient_id)).mappings().first()
    if not row:
        raise HTTPException(404, "Không tìm thấy hồ sơ.")
    return _public(row, user)


@router.put("/patients/{patient_id}")
def update_patient(patient_id: str, payload: PatientUpdate, user=Depends(current_user)):
    if not can_access_patient(user, patient_id):
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc bạn không được phân quyền.")
    values = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if user["role"] == "patient":
        forbidden = set(values) - {"phone", "email", "address"}
        if forbidden:
            raise HTTPException(403, "Bệnh nhân chỉ được tự cập nhật số điện thoại, email và địa chỉ.")
    if not values:
        raise HTTPException(422, "Không có trường hợp lệ để cập nhật.")
    values["updated_at"] = datetime.now(timezone.utc)
    with engine.begin() as con:
        con.execute(update(patient_profiles).where(patient_profiles.c.id == patient_id).values(**values))
    record(user["id"], "patient_updated", "patient", patient_id, {"fields": list(values)})
    return {"message": "Đã cập nhật hồ sơ bệnh nhân."}


@router.post("/patients/{patient_id}/records", status_code=201)
def create_record(patient_id: str, payload: RecordCreate, user=Depends(require_roles("admin", "staff"))):
    if not can_access_patient(user, patient_id, allow_patient=False):
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc bạn không được phân quyền.")
    record_id = str(uuid.uuid4())
    with engine.begin() as con:
        con.execute(insert(patient_records).values(
            id=record_id, patient_id=patient_id, created_by=user["id"],
            record_type=payload.record_type, record_data=payload.record_data,
            created_at=datetime.now(timezone.utc)))
    record(user["id"], "patient_record_created", "patient_record", record_id)
    return {"id": record_id, "message": "Đã lưu ghi chú hồ sơ."}


@router.get("/patients/{patient_id}/records")
def list_records(patient_id: str, user=Depends(current_user)):
    if not can_access_patient(user, patient_id):
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc bạn không được phân quyền.")
    with engine.connect() as con:
        rows = con.execute(select(patient_records).where(patient_records.c.patient_id == patient_id).order_by(patient_records.c.created_at.desc())).mappings().all()
    return {"items": [dict(r) for r in rows]}
