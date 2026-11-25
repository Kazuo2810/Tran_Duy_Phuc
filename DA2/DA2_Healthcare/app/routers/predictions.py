import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import insert
from ..schemas import PredictionRequest
from ..security import require_roles, can_access_patient
from ..database import engine, prediction_history
from ..audit import record

router = APIRouter(tags=["Dự đoán"])

def build_vector(payload, metadata):
    import numpy as np
    import pandas as pd
    expected = metadata["feature_names"]
    missing = sorted(set(expected) - set(payload.features))
    extra = sorted(set(payload.features) - set(expected))
    if missing or extra:
        raise HTTPException(422, detail={"missing": missing, "extra": extra})
    try:
        values = np.array([[payload.features[name] for name in expected]], dtype=float)
    except (TypeError, ValueError):
        raise HTTPException(422, "Tất cả 30 đặc trưng phải là số.")
    if not np.isfinite(values).all() or (values < 0).any():
        raise HTTPException(422, "Các đặc trưng phải là số hữu hạn không âm.")
    return pd.DataFrame(values, columns=expected)

def selected_model(model_key=None):
    from ..main import app
    key = model_key or app.state.default_model
    if key not in app.state.models:
        raise HTTPException(422, "Mô hình không hợp lệ. Chọn một trong 4 biến thể SVM.")
    return key, app.state.models[key], app.state.model_metadata[key]

def run_prediction(payload, model, metadata):
    x = build_vector(payload, metadata)
    predicted_class = int(model.predict(x)[0])
    probs = {int(c): float(v) for c, v in zip(model.classes_, model.predict_proba(x)[0])}
    return {
        "predicted_class": predicted_class,
        "predicted_label": metadata["class_mapping"][str(predicted_class)],
        "probability_malignant": probs[0], "probability_benign": probs[1],
        "model_key": metadata["model_key"], "model_name": metadata["model_name"],
        "model_version": metadata["model_version"], "warning": metadata["warning"],
    }

@router.post("/predict")
def public_predict(payload: PredictionRequest):
    """API minh họa không nhận dữ liệu định danh và không lưu lịch sử."""
    _, model, meta = selected_model(payload.model_key)
    return run_prediction(payload, model, meta)

@router.post("/api/patients/{patient_id}/predict")
def predict_for_patient(patient_id: str, payload: PredictionRequest, user=Depends(require_roles("admin", "staff"))):
    if not can_access_patient(user, patient_id, allow_patient=False):
        raise HTTPException(404, "Không tìm thấy hồ sơ hoặc bạn không được phân quyền.")
    key, model, meta = selected_model(payload.model_key)
    result = run_prediction(payload, model, meta)
    with engine.begin() as con:
        con.execute(insert(prediction_history).values(
            id=str(uuid.uuid4()), patient_id=patient_id, created_by=user["id"],
            model_name=meta["model_name"], model_version=meta["model_version"],
            features=payload.features, predicted_class=str(result["predicted_class"]),
            predicted_label=result["predicted_label"],
            probability_malignant=result["probability_malignant"],
            probability_benign=result["probability_benign"], created_at=datetime.now(timezone.utc)))
    record(user["id"], "prediction_created", "patient", patient_id,
           {"model_key": key, "model_version": result["model_version"]})
    return result
