from fastapi import APIRouter, HTTPException, Query
from .. import main

router = APIRouter(prefix="/api", tags=["Mô hình và dữ liệu"])

@router.get("/models")
def model_info():
    meta = main.app.state.metadata
    return {
        "model_name": meta["model_name"], "model_version": meta["model_version"],
        "default_model": main.app.state.default_model,
        "models": [
            {"model_key": key, "model_name": item["model_name"], "kernel": item["kernel"],
             "model_version": item["model_version"], "best_params": item["best_params"],
             "metrics": item["metrics"]}
            for key, item in main.app.state.model_metadata.items()
        ],
        "dataset": meta["dataset"], "feature_count": len(meta["feature_names"]),
        "feature_names": meta["feature_names"], "class_mapping": meta["class_mapping"],
        "metrics": meta["metrics"], "warning": meta["warning"],
    }

@router.get("/models/{model_key}")
def model_detail(model_key: str):
    item = main.app.state.model_metadata.get(model_key)
    if not item:
        raise HTTPException(404, "Không tìm thấy mô hình.")
    return item
