from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import joblib
import sqlite3
from datetime import datetime
import os

# Tải mô hình
model = joblib.load("svm_model.pkl")

app = FastAPI(title="Iris Classification API - Pro Version")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo Cơ sở dữ liệu SQLite
def init_db():
    conn = sqlite3.connect("iris_history.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            sepal_length REAL,
            sepal_width REAL,
            petal_length REAL,
            petal_width REAL,
            prediction TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class IrisInput(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

species = {0: "setosa", 1: "versicolor", 2: "virginica"}

# CỔNG GỐC: HIỂN THỊ GIAO DIỆN WEB
@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "Chưa tìm thấy file index.html"}

@app.get("/health")
def health():
    return {"status": "healthy"}

# MỞ CỬA CHO TRÌNH DUYỆT WEB (GET METHOD)
@app.get("/predict")
def predict_from_url(sl: float = 5.1, sw: float = 3.5, pl: float = 1.4, pw: float = 0.2):
    # 1. Dự đoán
    features = [[sl, sw, pl, pw]]
    pred_id = int(model.predict(features)[0])
    pred_name = species[pred_id]
    
    # 2. Lưu vào Database
    conn = sqlite3.connect("iris_history.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO predictions (timestamp, sepal_length, sepal_width, petal_length, petal_width, prediction) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sl, sw, pl, pw, pred_name)
    )
    conn.commit()
    conn.close()

    return {
        "thong_bao": "Đã nhận dữ liệu trực tiếp từ thanh địa chỉ trình duyệt!",
        "thong_so_nhan_duoc": {"sepal_length": sl, "sepal_width": sw, "petal_length": pl, "petal_width": pw},
        "class_id": pred_id, 
        "prediction": pred_name
    }

# DÀNH CHO GIAO DIỆN WEB INDEX.HTML (POST METHOD)
@app.post("/predict")
def predict(data: IrisInput):
    # 1. Dự đoán
    features = [[data.sepal_length, data.sepal_width, data.petal_length, data.petal_width]]
    pred_id = int(model.predict(features)[0])
    pred_name = species[pred_id]
    
    # 2. Lưu vào Database
    conn = sqlite3.connect("iris_history.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO predictions (timestamp, sepal_length, sepal_width, petal_length, petal_width, prediction) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data.sepal_length, data.sepal_width, data.petal_length, data.petal_width, pred_name)
    )
    conn.commit()
    conn.close()

    return {"class_id": pred_id, "prediction": pred_name}

@app.get("/history")
def get_history():
    conn = sqlite3.connect("iris_history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT prediction, COUNT(*) FROM predictions GROUP BY prediction")
    rows = cursor.fetchall()
    conn.close()
    
    # Trả về thống kê số lượng từng loài
    stats = {"setosa": 0, "versicolor": 0, "virginica": 0}
    for row in rows:
        if row[0] in stats:
            stats[row[0]] = row[1]
    return stats