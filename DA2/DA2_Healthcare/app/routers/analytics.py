"""Analytics, batch inference and model diagnostics for the WDBC learning app."""
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from ..security import current_user, require_roles

router = APIRouter(prefix="/api", tags=["Mô hình và dữ liệu"])

@router.get("/analytics/dataset")
def dataset_summary(user=Depends(current_user)):
    from sklearn.datasets import load_breast_cancer
    import pandas as pd
    data = load_breast_cancer(as_frame=True)
    frame = data.frame
    stats = frame.describe().T.reset_index().rename(columns={"index":"feature"})
    return {
        "dataset": "Wisconsin Diagnostic Breast Cancer (WDBC)",
        "samples": int(frame.shape[0]), "features": int(data.data.shape[1]),
        "class_counts": {"malignant": int((data.target == 0).sum()), "benign": int((data.target == 1).sum())},
        "feature_groups": {
            "mean": list(data.feature_names[:10]),
            "error": list(data.feature_names[10:20]),
            "worst": list(data.feature_names[20:30])
        },
        "statistics": stats.round(5).to_dict(orient="records"),
        "warning": "Thống kê bộ dữ liệu học tập, không đại diện cho quần thể lâm sàng."
    }

@router.get("/analytics/evaluation")
def evaluation(user=Depends(current_user)):
    from ..main import app
    metrics = app.state.metadata.get("metrics", {})
    return {
        "metrics": metrics,
        "confusion_matrix": metrics.get("confusion_matrix_labels_0_1", []),
        "labels": ["Ác tính", "Lành tính"],
        "warning": app.state.metadata.get("warning", "")
    }

@router.post("/predict/batch")
def batch_predict(payload: dict, user=Depends(require_roles("admin", "staff"))):
    """Batch inference accepts JSON; does not create patient records or persist inputs."""
    from ..main import app
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > 500:
        raise HTTPException(422, "Cần gửi từ 1 đến 500 dòng dữ liệu.")
    from .predictions import build_vector, run_prediction
    results = []
    for index, row in enumerate(rows, start=1):
        try:
            if not isinstance(row, dict) or not isinstance(row.get("features"), dict):
                raise ValueError("Mỗi dòng cần có trường features.")
            from types import SimpleNamespace
            result = run_prediction(SimpleNamespace(features=row["features"]), app.state.model, app.state.metadata)
            results.append({"row": index, **result})
        except Exception as exc:
            results.append({"row": index, "error": str(getattr(exc, "detail", exc))})
    return {"count": len(results), "items": results, "persisted": False,
            "warning": "Dự đoán hàng loạt không gắn hồ sơ bệnh nhân và không lưu lịch sử."}

@router.post("/predict/batch-csv")
def batch_predict_csv(payload: dict, user=Depends(require_roles("admin", "staff"))):
    """CSV text endpoint used by the browser after local file selection."""
    raw = payload.get("csv")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 2_000_000:
        raise HTTPException(422, "Nội dung CSV không hợp lệ hoặc vượt quá 2 MB.")
    from ..main import app
    from .predictions import run_prediction
    from types import SimpleNamespace
    expected = app.state.metadata["feature_names"]
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or not set(expected).issubset(set(reader.fieldnames)):
        raise HTTPException(422, "CSV phải có đủ 30 cột đặc trưng theo /metadata.")
    rows, results = list(reader), []
    if not rows or len(rows) > 500:
        raise HTTPException(422, "CSV cần có từ 1 đến 500 dòng.")
    for index, row in enumerate(rows, start=1):
        try:
            features = {name: float(row[name]) for name in expected}
            result = run_prediction(SimpleNamespace(features=features), app.state.model, app.state.metadata)
            results.append({"row": index, **result})
        except Exception as exc:
            results.append({"row": index, "error": str(getattr(exc, "detail", exc))})
    return {"count": len(results), "items": results, "persisted": False,
            "warning": "Dữ liệu CSV chỉ được xử lý để minh họa; không lưu vào hồ sơ."}
