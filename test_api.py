import requests

url = "https://tran-duy-phuc.onrender.com/predict"

# 4 thông số của một bông hoa Iris mà bạn muốn AI dự đoán
data = {
    "sepal_length": 5.1,
    "sepal_width": 3.5,
    "petal_length": 1.4,
    "petal_width": 0.2,
}

# Gửi dữ liệu lên mạng và in kết quả trả về
response = requests.post(url, json=data, timeout=30)
response.raise_for_status()
print("Kết quả AI dự đoán:", response.json())