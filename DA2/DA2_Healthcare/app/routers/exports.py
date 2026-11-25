from io import BytesIO
from fastapi import APIRouter, Depends, Query
from datetime import date, datetime, time, timedelta
from sqlalchemy import or_
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from ..database import engine, prediction_history, patient_profiles, staff_profiles, staff_patient_assignments
from ..security import current_user
from ..audit import record

router = APIRouter(prefix="/api", tags=["Xuất báo cáo"])

@router.get("/export")
def export_history(
    label: str = Query("", max_length=30),
    patient: str = Query("", max_length=100),
    start_date: str = Query("", max_length=10),
    end_date: str = Query("", max_length=10),
    user=Depends(current_user)
):
    q = select(prediction_history, patient_profiles.c.patient_code, patient_profiles.c.full_name.label("patient_name"))
    q = q.join(patient_profiles, patient_profiles.c.id == prediction_history.c.patient_id)
    if user["role"] == "patient":
        q = q.where(patient_profiles.c.user_id == user["id"])
    elif user["role"] == "staff":
        with engine.connect() as con:
            staff_id = con.execute(select(staff_profiles.c.id).where(staff_profiles.c.user_id == user["id"])).scalar_one_or_none()
        q = q.join(staff_patient_assignments, staff_patient_assignments.c.patient_id == patient_profiles.c.id).where(
            staff_patient_assignments.c.staff_id == staff_id,
            staff_patient_assignments.c.status == "active")
    if label in ("malignant", "benign"):
        q = q.where(prediction_history.c.predicted_label == label)
    if patient.strip():
        term = "%" + patient.strip() + "%"
        q = q.where(or_(patient_profiles.c.patient_code.ilike(term),
                        patient_profiles.c.full_name.ilike(term)))
    try:
        if start_date:
            q = q.where(prediction_history.c.created_at >= datetime.combine(date.fromisoformat(start_date), time.min))
        if end_date:
            q = q.where(prediction_history.c.created_at < datetime.combine(date.fromisoformat(end_date) + timedelta(days=1), time.min))
    except ValueError:
        raise HTTPException(422, "Ngày lọc phải theo định dạng YYYY-MM-DD.")
    with engine.connect() as con:
        rows = con.execute(q.order_by(prediction_history.c.created_at.desc())).mappings().all()
    wb = Workbook(); ws = wb.active; ws.title = "Lịch sử WDBC"
    ws.append(["Thời gian", "Mã bệnh nhân", "Họ tên", "Mô hình", "Phiên bản", "Kết quả", "P(ác tính)", "P(lành tính)", "Người thực hiện"])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="155E75")
        cell.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r["created_at"].isoformat() if r["created_at"] else "", r["patient_code"], r["patient_name"], r["model_name"], r["model_version"], r["predicted_label"], r["probability_malignant"], r["probability_benign"], r["created_by"]])
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        letter = col[0].column_letter
        ws.column_dimensions[letter].width = min(max(max(len(str(c.value or "")) for c in col) + 2, 12), 34)
    record(user["id"], "history_exported", "prediction_history", "", {"rows": len(rows)})
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=healthcare_prediction_history.xlsx"})
