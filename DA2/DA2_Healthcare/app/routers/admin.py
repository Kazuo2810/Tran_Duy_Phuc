import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, insert, update, and_
from ..database import engine, app_users, staff_profiles, patient_profiles, staff_patient_assignments, patient_records, prediction_history, audit_logs
from ..schemas import RoleUpdate, AssignmentCreate, StaffUpdate
from ..security import require_admin
from ..audit import record

router = APIRouter(prefix="/api/admin", tags=["Quản trị"])


@router.get("/users")
def list_users(user=Depends(require_admin)):
    with engine.connect() as con:
        rows = con.execute(select(app_users).order_by(app_users.c.created_at.desc())).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.patch("/users/{target_user_id}/role")
def update_user_role(target_user_id: str, payload: RoleUpdate, user=Depends(require_admin)):
    with engine.begin() as con:
        target = con.execute(select(app_users).where(app_users.c.id == target_user_id)).mappings().first()
        if not target:
            raise HTTPException(404, "Không tìm thấy tài khoản trong Healthcare. Người dùng cần đăng nhập ít nhất một lần.")
        if target_user_id == user["id"] and payload.role != "admin":
            raise HTTPException(409, "Không thể tự hạ quyền Admin đang đăng nhập.")
        con.execute(update(app_users).where(app_users.c.id == target_user_id).values(role=payload.role))
        if payload.role == "staff":
            exists = con.execute(select(staff_profiles.c.id).where(staff_profiles.c.user_id == target_user_id)).first()
            if not exists:
                con.execute(insert(staff_profiles).values(
                    id=str(uuid.uuid4()), user_id=target_user_id,
                    full_name=target["display_name"], department="", position="", phone="",
                    created_at=datetime.now(timezone.utc)))
        elif payload.role == "patient":
            exists = con.execute(select(patient_profiles.c.id).where(patient_profiles.c.user_id == target_user_id)).first()
            if not exists:
                con.execute(insert(patient_profiles).values(
                    id=str(uuid.uuid4()), user_id=target_user_id,
                    patient_code="P-" + uuid.uuid4().hex[:8].upper(),
                    full_name=target["display_name"], gender="", phone="", email="", address="", notes="",
                    created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
    record(user["id"], "user_role_changed", "app_user", target_user_id, {"role": payload.role})
    return {"message": "Đã cập nhật vai trò.", "user_id": target_user_id, "role": payload.role}


@router.get("/staff")
def list_staff(user=Depends(require_admin)):
    with engine.connect() as con:
        rows = con.execute(select(staff_profiles, app_users.c.username, app_users.c.status)
            .join(app_users, app_users.c.id == staff_profiles.c.user_id)
            .order_by(staff_profiles.c.full_name)).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.put("/staff/{staff_id}")
def update_staff(staff_id: str, payload: StaffUpdate, user=Depends(require_admin)):
    with engine.begin() as con:
        result = con.execute(update(staff_profiles).where(staff_profiles.c.id == staff_id).values(**payload.model_dump()))
        if not result.rowcount:
            raise HTTPException(404, "Không tìm thấy hồ sơ nhân viên.")
    record(user["id"], "staff_profile_updated", "staff", staff_id)
    return {"message": "Đã cập nhật hồ sơ nhân viên."}


@router.get("/assignments")
def list_assignments(user=Depends(require_admin)):
    q = select(
        staff_patient_assignments,
        staff_profiles.c.full_name.label("staff_name"),
        patient_profiles.c.patient_code,
        patient_profiles.c.full_name.label("patient_name"),
    ).join(staff_profiles, staff_profiles.c.id == staff_patient_assignments.c.staff_id)
    q = q.join(patient_profiles, patient_profiles.c.id == staff_patient_assignments.c.patient_id)
    with engine.connect() as con:
        rows = con.execute(q.order_by(staff_patient_assignments.c.assigned_at.desc())).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("/assignments", status_code=201)
def create_assignment(payload: AssignmentCreate, user=Depends(require_admin)):
    with engine.begin() as con:
        staff_id = con.execute(select(staff_profiles.c.id).where(staff_profiles.c.user_id == payload.staff_user_id)).scalar_one_or_none()
        patient = con.execute(select(patient_profiles.c.id).where(patient_profiles.c.id == payload.patient_id)).first()
        if not staff_id or not patient:
            raise HTTPException(404, "Không tìm thấy nhân viên hoặc bệnh nhân.")
        existing = con.execute(select(staff_patient_assignments).where(
            staff_patient_assignments.c.staff_id == staff_id,
            staff_patient_assignments.c.patient_id == payload.patient_id)).mappings().first()
        if existing:
            con.execute(update(staff_patient_assignments).where(staff_patient_assignments.c.id == existing["id"]).values(status="active", assigned_by=user["id"], assigned_at=datetime.now(timezone.utc)))
            assignment_id = existing["id"]
        else:
            assignment_id = str(uuid.uuid4())
            con.execute(insert(staff_patient_assignments).values(
                id=assignment_id, staff_id=staff_id, patient_id=payload.patient_id,
                assigned_by=user["id"], assigned_at=datetime.now(timezone.utc), status="active"))
    record(user["id"], "patient_assigned", "assignment", assignment_id, {"staff_user_id": payload.staff_user_id, "patient_id": payload.patient_id})
    return {"id": assignment_id, "message": "Đã phân công bệnh nhân cho nhân viên."}


@router.delete("/assignments/{assignment_id}")
def deactivate_assignment(assignment_id: str, user=Depends(require_admin)):
    with engine.begin() as con:
        result = con.execute(update(staff_patient_assignments).where(
            staff_patient_assignments.c.id == assignment_id).values(status="inactive"))
        if not result.rowcount:
            raise HTTPException(404, "Không tìm thấy phân công.")
    record(user["id"], "assignment_deactivated", "assignment", assignment_id)
    return {"message": "Đã ngừng phân công."}


@router.get("/audit-logs")
def list_audit_logs(limit: int = 100, user=Depends(require_admin)):
    limit = max(1, min(limit, 500))
    with engine.connect() as con:
        rows = con.execute(select(audit_logs).order_by(audit_logs.c.created_at.desc()).limit(limit)).mappings().all()
    return {"items": [dict(r) for r in rows]}

@router.delete("/audit-logs")
def delete_audit_logs(payload: dict, user=Depends(require_admin)):
    ids = list(dict.fromkeys(str(x) for x in (payload.get("ids") or []) if str(x).strip()))
    if not ids:
        raise HTTPException(422, "Hãy chọn ít nhất một mục lịch sử cần xóa.")
    if len(ids) > 100:
        raise HTTPException(422, "Mỗi lần chỉ được xóa tối đa 100 mục.")
    with engine.begin() as con:
        result = con.execute(audit_logs.delete().where(audit_logs.c.id.in_(ids)))
        deleted_count = result.rowcount or 0
    record(user["id"], "audit_logs_deleted", "audit_logs", "", {"deleted_count": deleted_count})
    return {"message": f"Đã xóa {deleted_count} mục lịch sử.", "deleted_count": deleted_count}

@router.post("/patients/{patient_id}/link-account")
def link_patient_account(patient_id: str, payload: dict, user=Depends(require_admin)):
    target_user_id = str(payload.get("user_id", "")).strip()
    if not target_user_id:
        raise HTTPException(422, "Thiếu user_id.")
    with engine.begin() as con:
        account = con.execute(select(app_users).where(app_users.c.id == target_user_id)).mappings().first()
        patient = con.execute(select(patient_profiles).where(patient_profiles.c.id == patient_id)).mappings().first()
        if not account or account["role"] != "patient" or not patient:
            raise HTTPException(404, "Không tìm thấy tài khoản bệnh nhân hoặc hồ sơ.")
        linked = con.execute(select(patient_profiles.c.id).where(
            patient_profiles.c.user_id == target_user_id,
            patient_profiles.c.id != patient_id)).scalar_one_or_none()
        if linked:
            has_records = con.execute(select(patient_records.c.id).where(patient_records.c.patient_id == linked).limit(1)).first()
            has_predictions = con.execute(select(prediction_history.c.id).where(prediction_history.c.patient_id == linked).limit(1)).first()
            if has_records or has_predictions:
                raise HTTPException(409, "Tài khoản đã có hồ sơ phát sinh dữ liệu; không thể tự động gộp hồ sơ.")
            con.execute(patient_profiles.delete().where(patient_profiles.c.id == linked))
        con.execute(update(patient_profiles).where(patient_profiles.c.id == patient_id).values(
            user_id=target_user_id, updated_at=datetime.now(timezone.utc)))
    record(user["id"], "patient_account_linked", "patient", patient_id, {"user_id": target_user_id})
    return {"message": "Đã liên kết tài khoản bệnh nhân với hồ sơ."}
