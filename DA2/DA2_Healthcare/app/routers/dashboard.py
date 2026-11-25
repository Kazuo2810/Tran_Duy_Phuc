from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from ..database import engine, app_users, patient_profiles, staff_profiles, prediction_history
from ..security import current_user

router = APIRouter(prefix="/api", tags=["Tổng quan"])

@router.get("/dashboard/summary")
def summary(user=Depends(current_user)):
    with engine.connect() as con:
        if user["role"] == "admin":
            patients = con.execute(select(func.count()).select_from(patient_profiles)).scalar_one()
            staff = con.execute(select(func.count()).select_from(staff_profiles)).scalar_one()
            predictions = con.execute(select(func.count()).select_from(prediction_history)).scalar_one()
            users = con.execute(select(func.count()).select_from(app_users)).scalar_one()
        elif user["role"] == "staff":
            from ..database import staff_patient_assignments
            staff_id = con.execute(select(staff_profiles.c.id).where(staff_profiles.c.user_id == user["id"])).scalar_one_or_none()
            patients = con.execute(select(func.count()).select_from(staff_patient_assignments).where(
                staff_patient_assignments.c.staff_id == staff_id,
                staff_patient_assignments.c.status == "active")).scalar_one() if staff_id else 0
            staff, users = 1, 1
            predictions = con.execute(select(func.count()).select_from(prediction_history).join(
                patient_profiles, patient_profiles.c.id == prediction_history.c.patient_id).join(
                staff_patient_assignments, staff_patient_assignments.c.patient_id == patient_profiles.c.id).where(
                staff_patient_assignments.c.staff_id == staff_id,
                staff_patient_assignments.c.status == "active")).scalar_one() if staff_id else 0
        else:
            patients = 1 if con.execute(select(patient_profiles.c.id).where(patient_profiles.c.user_id == user["id"])).first() else 0
            staff, users = 0, 1
            predictions = con.execute(select(func.count()).select_from(prediction_history).join(
                patient_profiles, patient_profiles.c.id == prediction_history.c.patient_id).where(
                patient_profiles.c.user_id == user["id"])).scalar_one()
    return {"role": user["role"], "patients": patients, "staff": staff, "predictions": predictions, "users": users}
