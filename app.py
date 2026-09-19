from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib

# Tải mô hình đã huấn luyện (Giống Bước 5)
model = joblib.load("svm_model.pkl")

# Khởi tạo FastAPI (Giống Bước 5)
app = FastAPI(
    title="Iris Classification API",
    description="SVM model for the Iris dataset",
    version="1.0.0",
)

# Cấp quyền CORS để HTML cục bộ gọi được API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khai báo schema đầu vào (Giống Bước 5)
class IrisInput(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

# Khai báo nhãn (Giống Bước 6)
species = {0: "setosa", 1: "versicolor", 2: "virginica"}

# Endpoint gốc (Giống Bước 6)
@app.get("/")
def home():
    return {"message": "Iris SVM API is running"}

# Endpoint kiểm tra sức khỏe (Giống Bước 6)
@app.get("/health")
def health():
    return {"status": "healthy"}

# Endpoint dự đoán phân loại (Giống Bước 7)
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