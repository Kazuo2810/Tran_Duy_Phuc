from fastapi import APIRouter
from .. import main

router = APIRouter(prefix="/api", tags=["Mô hình và dữ liệu"])

@router.get("/models")
def model_info():
    meta = main.app.state.metadata
    return {
        "model_name": meta["model_name"], "model_version": meta["model_version"],
        "dataset": meta["dataset"], "feature_count": len(meta["feature_names"]),
        "feature_names": meta["feature_names"], "class_mapping": meta["class_mapping"],
        "metrics": meta["metrics"], "warning": meta["warning"],
    }
