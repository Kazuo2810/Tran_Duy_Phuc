from sklearn import datasets
from sklearn.svm import SVC
import joblib

# Tải dữ liệu Iris
iris = datasets.load_iris()
X = iris.data
y = iris.target

# Khởi tạo và huấn luyện mô hình SVM (kernel linear)
model = SVC(kernel="linear")
model.fit(X, y)

# Lưu mô hình đã huấn luyện
joblib.dump(model, "svm_model.pkl")
print("Model saved!")

