"""Healthcare/WDBC app: shared IdP, isolated healthcare schema, role-based patient access."""
from contextlib import asynccontextmanager
from pathlib import Path
import hashlib, json
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
    model_path = ROOT / "artifacts/breast_cancer_svm.joblib"
    meta = json.loads((ROOT / "artifacts/metadata.json").read_text(encoding="utf-8"))
    if meta["sklearn_version"] != sklearn.__version__:
        raise RuntimeError("Phiên bản scikit-learn khác môi trường tạo artifact.")
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != meta["model_sha256"]:
        raise RuntimeError("Artifact không khớp checksum trong metadata.")
    model = joblib.load(model_path)
    if len(meta["feature_names"]) != 30 or list(model.feature_names_in_) != meta["feature_names"]:
        raise RuntimeError("Thứ tự/tên 30 đặc trưng không khớp model.")
    if list(model.classes_) != [0, 1] or meta["class_mapping"] != {"0": "malignant", "1": "benign"}:
        raise RuntimeError("Ánh xạ nhãn WDBC không hợp lệ.")
    app.state.model, app.state.metadata = model, meta
    yield

app = FastAPI(
    title="Healthcare – Hồ sơ bệnh nhân & phân loại WDBC",
    version="2.0.0",
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
    return {"status": "ok", "model_loaded": app.state.model is not None,
            "model_version": app.state.metadata["model_version"], "database_schema": "healthcare"}

@app.get("/metadata")
def metadata():
    return app.state.metadata

@app.get("/api/sample")
def sample():
    return json.loads((ROOT / "sample_request.json").read_text(encoding="utf-8"))

@app.get("/", include_in_schema=False)
def website():
    return FileResponse(ROOT / "web/index.html")

app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
