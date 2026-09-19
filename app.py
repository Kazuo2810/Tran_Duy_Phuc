from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import joblib
import os

# Tải mô hình đã huấn luyện
model = joblib.load("svm_model.pkl")

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="Iris Classification API",
    description="SVM model for the Iris dataset",
    version="1.0.0",
)

# Cấp quyền CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khai báo schema đầu vào
class IrisInput(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

# Khai báo nhãn
species = {0: "setosa", 1: "versicolor", 2: "virginica"}

# Endpoint gốc: Tích hợp Giao diện (Interface / index.html)
@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "Iris SVM API is running"}

# Endpoint kiểm tra sức khỏe
@app.get("/health")
def health():
    return {"status": "healthy"}

# Endpoint dự đoán phân loại
@app.post("/predict")
def predict(data: IrisInput):
    features = [[
        data.sepal_length,
        data.sepal_width,
        data.petal_length,
        data.petal_width
    ]]
    prediction = int(model.predict(features)[0])
    return {
        "class_id": prediction,
        "prediction": species[prediction]
    }