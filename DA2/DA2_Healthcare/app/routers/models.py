from fastapi import APIRouter, HTTPException, Query
import secrets
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


def _wdbc_example(index, title, description):
    from sklearn.datasets import load_breast_cancer
    data = load_breast_cancer(as_frame=True)
    row = data.data.iloc[index]
    target = int(data.target.iloc[index])
    return {
        "title": title, "description": description,
        "features": {name: float(value) for name, value in row.items()},
        "dataset_label": "malignant" if target == 0 else "benign",
        "source": "WDBC sample dataset",
    }

@router.get("/samples")
def example_samples():
    """Hai dòng ví dụ trong WDBC, không phải hồ sơ bệnh nhân."""
    from sklearn.datasets import load_breast_cancer
    data = load_breast_cancer()
    benign_index = int(next(i for i, target in enumerate(data.target) if int(target) == 1))
    return {
        "items": [
            _wdbc_example(0, "Ví dụ 1 · Mẫu thuộc nhóm ác tính", "Mẫu có nhãn gốc malignant trong WDBC."),
            _wdbc_example(benign_index, "Ví dụ 2 · Mẫu thuộc nhóm lành tính", "Mẫu có nhãn gốc benign trong WDBC."),
        ],
        "warning": "Dữ liệu WDBC phục vụ học tập, không phải dữ liệu bệnh nhân thật."
    }

@router.get("/sample/random")
def random_sample():
    """Chọn ngẫu nhiên một dòng trong bộ dữ liệu WDBC."""
    from sklearn.datasets import load_breast_cancer
    data = load_breast_cancer(as_frame=True)
    index = secrets.randbelow(len(data.data))
    target = int(data.target.iloc[index])
    return {
        "title": "Mẫu ngẫu nhiên từ WDBC",
        "features": {name: float(value) for name, value in data.data.iloc[index].items()},
        "dataset_label": "malignant" if target == 0 else "benign",
        "source": "WDBC sample dataset",
        "warning": "Giá trị lấy từ dữ liệu học tập, không phải dữ liệu bệnh nhân thật."
    }

@router.get("/models/{model_key}")
def model_detail(model_key: str):
    item = main.app.state.model_metadata.get(model_key)
    if not item:
        raise HTTPException(404, "Không tìm thấy mô hình.")
    return item
