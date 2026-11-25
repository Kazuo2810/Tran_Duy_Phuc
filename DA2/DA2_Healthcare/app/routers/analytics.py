"""Analytics, batch inference and model diagnostics for the WDBC learning app."""
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from ..security import current_user, require_roles

router = APIRouter(prefix="/api", tags=["Mô hình và dữ liệu"])

def get_model(model_key=None):
    from ..main import app
    key = model_key or app.state.default_model
    if key not in app.state.models:
        raise HTTPException(422, "Mô hình không hợp lệ. Chọn một trong 4 biến thể SVM.")
    return key, app.state.models[key], app.state.model_metadata[key]

@router.get("/analytics/dataset")
def dataset_summary(user=Depends(current_user)):
    from sklearn.datasets import load_breast_cancer
    data = load_breast_cancer(as_frame=True)
    frame = data.frame
    stats = frame.describe().T.reset_index().rename(columns={"index":"feature"})
    return {
        "dataset": "Wisconsin Diagnostic Breast Cancer (WDBC)",
        "samples": int(frame.shape[0]), "features": int(data.data.shape[1]),
        "class_counts": {"malignant": int((data.target == 0).sum()), "benign": int((data.target == 1).sum())},
        "feature_groups": {"mean": list(data.feature_names[:10]),
            "error": list(data.feature_names[10:20]), "worst": list(data.feature_names[20:30])},
        "statistics": stats.round(5).to_dict(orient="records"),
        "warning": "Thống kê bộ dữ liệu học tập, không đại diện cho quần thể lâm sàng."
    }

@router.get("/analytics/evaluation")
def evaluation(model_key: str | None = Query(default=None), user=Depends(current_user)):
    key, _, meta = get_model(model_key)
    metrics = meta["metrics"]
    return {"model_key": key, "model_name": meta["model_name"], "metrics": metrics,
        "confusion_matrix": metrics.get("confusion_matrix_labels_0_1", []),
        "labels": ["Ác tính", "Lành tính"], "warning": meta["warning"]}

@router.post("/predict/batch")
def batch_predict(payload: dict, user=Depends(require_roles("admin", "staff"))):
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > 500:
        raise HTTPException(422, "Cần gửi từ 1 đến 500 dòng dữ liệu.")
    _, model, meta = get_model(payload.get("model_key"))
    from .predictions import build_vector, run_prediction
    results = []
    for index, row in enumerate(rows, start=1):
        try:
            if not isinstance(row, dict) or not isinstance(row.get("features"), dict):
                raise ValueError("Mỗi dòng cần có trường features.")
            from types import SimpleNamespace
            result = run_prediction(SimpleNamespace(features=row["features"]), model, meta)
            results.append({"row": index, **result})
        except Exception as exc:
            results.append({"row": index, "error": str(getattr(exc, "detail", exc))})
    return {"count": len(results), "items": results, "persisted": False,
        "warning": "Dự đoán hàng loạt không gắn hồ sơ bệnh nhân và không lưu lịch sử."}

@router.post("/predict/batch-csv")
def batch_predict_csv(payload: dict, user=Depends(require_roles("admin", "staff"))):
    raw = payload.get("csv")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 2_000_000:
        raise HTTPException(422, "Nội dung CSV không hợp lệ hoặc vượt quá 2 MB.")
    _, model, meta = get_model(payload.get("model_key"))
    from .predictions import run_prediction
    from types import SimpleNamespace
    expected = meta["feature_names"]
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or not set(expected).issubset(set(reader.fieldnames)):
        raise HTTPException(422, "CSV phải có đủ 30 cột đặc trưng theo /metadata.")
    rows, results = list(reader), []
    if not rows or len(rows) > 500:
        raise HTTPException(422, "CSV cần có từ 1 đến 500 dòng.")
    for index, row in enumerate(rows, start=1):
        try:
            features = {name: float(row[name]) for name in expected}
            result = run_prediction(SimpleNamespace(features=features), model, meta)
            results.append({"row": index, **result})
        except Exception as exc:
            results.append({"row": index, "error": str(getattr(exc, "detail", exc))})
    return {"count": len(results), "items": results, "persisted": False,
        "warning": "Dữ liệu CSV chỉ được xử lý để minh họa; không lưu vào hồ sơ."}

@router.get("/analytics/decision-slice")
def decision_slice(
    x_feature: str = Query("mean radius", max_length=80),
    y_feature: str = Query("mean texture", max_length=80),
    model_key: str | None = Query(default=None),
    user=Depends(current_user)
):
    import numpy as np
    import pandas as pd
    from sklearn.datasets import load_breast_cancer
    key, model, meta = get_model(model_key)
    names = meta["feature_names"]
    if x_feature not in names or y_feature not in names or x_feature == y_feature:
        raise HTTPException(422, "Hãy chọn hai đặc trưng khác nhau trong danh sách WDBC.")
    data = load_breast_cancer(as_frame=True).data
    x_min, x_max = float(data[x_feature].quantile(.02)), float(data[x_feature].quantile(.98))
    y_min, y_max = float(data[y_feature].quantile(.02)), float(data[y_feature].quantile(.98))
    gx, gy = np.linspace(x_min, x_max, 35), np.linspace(y_min, y_max, 35)
    xx, yy = np.meshgrid(gx, gy)
    grid = pd.DataFrame(np.tile(data.median().to_numpy(), (xx.size, 1)), columns=names)
    grid[x_feature], grid[y_feature] = xx.ravel(), yy.ravel()
    decision = model.decision_function(grid).reshape(xx.shape)
    points = data[[x_feature, y_feature]].to_numpy()
    labels = load_breast_cancer().target.astype(int)
    return {"model_key": key, "x_feature": x_feature, "y_feature": y_feature,
        "x": gx.tolist(), "y": gy.tolist(), "decision": decision.tolist(),
        "points": [{"x": float(a), "y": float(b), "label": int(label)}
                   for (a, b), label in zip(points, labels)],
        "fixed_features": "Các đặc trưng còn lại được cố định tại trung vị WDBC.",
        "warning": "Đây là lát cắt 2D của không gian 30 chiều, không phải biên quyết định đầy đủ."}
