from fastapi import FastAPI
from pydantic import BaseModel
import joblib

# Tải mô hình đã lưu
model = joblib.load("svm_model.pkl")

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="Iris Classification API",
    description="SVM model for the Iris dataset",
    version="1.0.0",
)

# Định nghĩa cấu trúc dữ liệu đầu vào
class IrisInput(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

# Định nghĩa từ điển nhãn tên loài hoa
species = {
    0: "setosa",
    1: "versicolor",
    2: "virginica"
}

# Endpoint gốc
@app.get("/")
def home():
    return {"message": "Iris SVM API is running"}

# Endpoint kiểm tra trạng thái (Health check)
@app.get("/health")
def health():
    return {"status": "healthy"}

# Endpoint dự đoán
@app.post("/predict")
def predict(data: IrisInput):
    # Trích xuất đặc trưng từ input
    features = [[
        data.sepal_length,
        data.sepal_width,
        data.petal_length,
        data.petal_width,
    ]]
    
    # Thực hiện dự đoán
    prediction = int(model.predict(features)[0])
    
    # Trả về kết quả JSON
    return {
        "class_id": prediction,
        "prediction": species[prediction],
    }