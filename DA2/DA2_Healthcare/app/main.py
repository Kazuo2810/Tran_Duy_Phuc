"""Healthcare/WDBC app: Shared IdP, isolated healthcare schema, role-based patient access."""
from contextlib import asynccontextmanager
from pathlib import Path
import hashlib, json, subprocess, sys
import joblib
import sklearn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .database import init_db
from .routers import auth, admin, patients, predictions, history, models, exports, dashboard, analytics

ROOT = Path(__file__).resolve().parents[1]

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    metadata_path = ROOT / "artifacts/metadata.json"
    try:
        current_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        current_meta = {}
    required = [
        ROOT / "artifacts" / "models" / key / "deployment.joblib"
        for key in ("SVM_LINEAR", "SVM_RBF", "SVM_POLY", "SVM_SIGMOID")
    ]
    if len(current_meta.get("models", {})) != 4 or not all(path.is_file() for path in required):
        subprocess.run([sys.executable, str(ROOT / "scripts/train.py")], cwd=ROOT, check=True)
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    if meta["sklearn_version"] != sklearn.__version__:
        raise RuntimeError("Phiên bản scikit-learn khác môi trường tạo artifact.")
    loaded, metadata_by_key = {}, {}
    for key, item in meta["models"].items():
        path = ROOT / "artifacts" / "models" / key / "deployment.joblib"
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["deployment_sha256"]:
            raise RuntimeError(f"Artifact {key} không khớp checksum metadata.")
        model = joblib.load(path)
        if list(model.feature_names_in_) != meta["feature_names"]:
            raise RuntimeError(f"Thứ tự/tên đặc trưng không khớp model {key}.")
        if list(model.classes_) != [0, 1]:
            raise RuntimeError(f"Ánh xạ nhãn model {key} không hợp lệ.")
        loaded[key] = model
        metadata_by_key[key] = item
    default_key = meta["default_model"]
    app.state.models = loaded
    app.state.model_metadata = metadata_by_key
    app.state.default_model = default_key
    app.state.model = loaded[default_key]
    app.state.metadata = {
        **meta,
        "model_name": metadata_by_key[default_key]["model_name"],
        "model_version": metadata_by_key[default_key]["model_version"],
        "metrics": metadata_by_key[default_key]["metrics"],
        "best_params": metadata_by_key[default_key]["best_params"],
    }
    yield

app = FastAPI(
    title="Healthcare – Hồ sơ bệnh nhân & 4 mô hình SVM WDBC",
    version="3.0.0",
    description="Ứng dụng học tập; kết quả WDBC không phải chẩn đoán y tế.",
    lifespan=lifespan,
    openapi_tags=[{"name": n} for n in ["Xác thực", "Tổng quan", "Hồ sơ bệnh nhân", "Quản trị", "Dự đoán", "Lịch sử", "Mô hình và dữ liệu", "Xuất báo cáo"]],
)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(patients.router)
app.include_router(admin.router)
app.include_router(predictions.router)
app.include_router(history.router)
app.include_router(models.router)
app.include_router(exports.router)

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": len(app.state.models) == 4,
            "model_count": len(app.state.models), "default_model": app.state.default_model,
            "database_schema": "healthcare"}

@app.get("/metadata")
def metadata():
    return app.state.metadata

@app.get("/api/sample")
def sample():
    return json.loads((ROOT / "sample_request.json").read_text(encoding="utf-8"))

@app.get("/", include_in_schema=False)
def website():
    return FileResponse(ROOT / "web/index.html")

app.mount("/static", StaticFiles(directory=ROOT / "web/static"), name="static")
