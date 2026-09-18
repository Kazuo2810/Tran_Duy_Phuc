from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib

# Tải mô hình SVM đã huấn luyện
model = joblib.load("svm_model.pkl")

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="Iris Classification API",
    description="SVM model for the Iris dataset",
    version="1.0.0",
)

# Cấu hình CORS để cho phép các trang web bên ngoài gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Định nghĩa cấu trúc dữ liệu đầu vào
class IrisInput(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

# Từ điển ánh xạ kết quả
species = {
    0: "setosa",
    1: "versicolor",
    2: "virginica",
}

# Endpoint gốc
@app.get("/")
def home():
    return {"message": "Iris SVM API is running"}

# Endpoint kiểm tra sức khỏe máy chủ
@app.get("/health")
def health():
    return {"status": "healthy"}

# Endpoint dự đoán
@app.post("/predict")
def predict(data: IrisInput):
    features = [[
        data.sepal_length,
        data.sepal_width,
        data.petal_length,
        data.petal_width,
    ]]
    prediction = int(model.predict(features)[0])
    return {
        "class_id": prediction,
        "prediction": species[prediction],
    }