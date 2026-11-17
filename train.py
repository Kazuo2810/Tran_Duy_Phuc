"""Quy trình huấn luyện, đánh giá độc lập và đóng gói 5 cấu hình SVM cho bộ dữ liệu Iris.

Quy trình khoa học dữ liệu được áp dụng:
1. Chia dữ liệu theo tỷ lệ 80% Train (120 mẫu) / 20% Test (30 mẫu) có phân tầng (stratify).
2. Mọi mô hình đều nằm trong Pipeline với StandardScaler để tránh rò rỉ dữ liệu (Data Leakage).
3. Đánh giá bằng 5-Fold Stratified Cross-Validation trên tập Train (riêng SVM_OPT dùng Nested CV).
4. Lưu song song 2 bản mô hình:
   - evaluation.joblib: Mô hình fit trên 120 mẫu Train (dùng để báo cáo chỉ số khách quan).
   - deployment.joblib: Mô hình fit lại trên toàn bộ 150 mẫu (dùng để phục vụ dự đoán thực tế).
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.datasets import load_iris
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import (
    GridSearchCV,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parent

# Từ điển ánh xạ mã mô hình (tối đa 8 ký tự để khớp cột SQL) sang tên hiển thị đầy đủ
MODEL_NAMES = {
    "SVM": "SVM Linear",
    "SVM_RBF": "SVM RBF",
    "SVM_POLY": "SVM Polynomial",
    "SVM_SIG": "SVM Sigmoid",
    "SVM_OPT": "SVM RBF tối ưu tham số (GridSearchCV)",
}

# Tên cột đặc trưng kỹ thuật và nhãn tiếng Việt tương ứng
FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
LABELS = [
    "Chiều dài đài hoa",
    "Chiều rộng đài hoa",
    "Chiều dài cánh hoa",
    "Chiều rộng cánh hoa",
]


def estimators() -> dict:
    """Khởi tạo 4 cấu hình SVM tham số cố định và 1 cấu hình tối ưu siêu tham số tự động."""
    # Helper tạo Pipeline chuẩn hóa dữ liệu trước khi đưa vào bộ phân lớp SVC
    scaled_svc = lambda **kwargs: make_pipeline(StandardScaler(), SVC(**kwargs))

    # Cấu hình tìm kiếm lưới (Grid Search) 4x4 = 16 tổ hợp tham số (C, gamma) cho kernel RBF
    tuned_svm = GridSearchCV(
        estimator=scaled_svc(),
        param_grid={
            "svc__C": [0.1, 1, 10, 100],
            "svc__gamma": ["scale", 0.01, 0.1, 1],
        },
        scoring="accuracy",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
        n_jobs=1,
        refit=True,
    )
    return {
        "SVM": scaled_svc(kernel="linear", C=1.0),
        "SVM_RBF": scaled_svc(kernel="rbf", C=1.0, gamma="scale"),
        "SVM_POLY": scaled_svc(kernel="poly", C=1.0, degree=3, gamma="scale"),
        "SVM_SIG": scaled_svc(kernel="sigmoid", C=1.0, gamma="scale"),
        "SVM_OPT": tuned_svm,
    }


def _json_parameters(estimator, tuned_search=None) -> dict:
    """Trích xuất tham số cấu hình của mô hình sang định dạng từ điển thuần để lưu JSON."""
    if tuned_search is not None:
        return {
            "method": "GridSearchCV",
            "best_params": tuned_search.best_params_,
            "best_cv_accuracy": float(tuned_search.best_score_),
            "candidate_count": len(tuned_search.cv_results_["params"]),
        }
    return {
        key: value
        for key, value in estimator.get_params().items()
        if isinstance(value, (str, int, float, bool, type(None)))
    }


def train_all(output: Path = ROOT / "models"):
    """Thực thi huấn luyện, kiểm thử và xuất file artifact cho cả 5 cấu hình SVM."""
    iris = load_iris()
    X, y = iris.data, iris.target

    # Chia tập Train/Test theo chỉ số (indices) để lưu lại dấu vết mẫu dữ liệu trong báo cáo
    train_indices, test_indices = train_test_split(
        np.arange(len(y)),
        test_size=0.2,
        random_state=42,
        stratify=y,
    )
    X_train, y_train = X[train_indices], y[train_indices]
    X_test, y_test = X[test_indices], y[test_indices]

    cv_splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    output.mkdir(parents=True, exist_ok=True)

    for key, estimator in estimators().items():
        folder = output / key
        folder.mkdir(parents=True, exist_ok=True)
        tuned_search = None

        if key == "SVM_OPT":
            # 1. Tìm tham số tốt nhất trên tập Train (120 mẫu) để đánh giá trên Test (30 mẫu)
            tuned_search = clone(estimator).fit(X_train, y_train)
            evaluation = tuned_search.best_estimator_

            # 2. Nested Cross-Validation: mỗi fold tự tìm tham số độc lập để tránh lạc quan quá mức
            cv_scores = cross_val_score(
                clone(estimator), X_train, y_train,
                cv=cv_splitter, scoring="accuracy", n_jobs=1,
            )

            # 3. Huấn luyện lại trên toàn bộ 150 mẫu để triển khai thực tế
            deployed_search = clone(estimator).fit(X, y)
            deployed = deployed_search.best_estimator_

            parameters = _json_parameters(estimator, tuned_search)
            parameters["deployment_best_params"] = deployed_search.best_params_
        else:
            evaluation = clone(estimator).fit(X_train, y_train)
            cv_scores = cross_val_score(
                clone(estimator), X_train, y_train,
                cv=cv_splitter, scoring="accuracy", n_jobs=1,
            )
            deployed = clone(estimator).fit(X, y)
            parameters = _json_parameters(estimator)

        # Đánh giá hiệu năng trên tập Test độc lập (30 mẫu)
        predictions = evaluation.predict(X_test)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_test, predictions, average="macro", zero_division=0
        )

        # Lưu file mô hình và tạo mã băm phiên bản (12 ký tự đầu của SHA-256)
        joblib.dump(evaluation, folder / "evaluation.joblib")
        joblib.dump(deployed, folder / "deployment.joblib")
        version = hashlib.sha256(
            (folder / "deployment.joblib").read_bytes()
        ).hexdigest()[:12]

        # Tổng hợp toàn bộ siêu dữ liệu và chỉ số đánh giá vào report.json
        report = {
            "model": key,
            "name": MODEL_NAMES[key],
            "version": version,
            "sklearn_version": sklearn.__version__,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "metric_scale": "0–1",
            "average": "macro",
            "train_count": len(train_indices),
            "test_count": len(test_indices),
            "deployment_count": len(y),
            "random_state": 42,
            "train_indices": train_indices.tolist(),
            "test_indices": test_indices.tolist(),
            "parameters": parameters,
            "test_accuracy": float(accuracy_score(y_test, predictions)),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "cv_accuracy": float(cv_scores.mean()),
            "cv_std": float(cv_scores.std()),
            "cv_scores": cv_scores.tolist(),
            "cv_scope": (
                "5-fold trên 120 mẫu train; StandardScaler được fit riêng trong từng fold. "
                + ("SVM_OPT dùng GridSearchCV lồng trong từng fold." if key == "SVM_OPT" else "")
            ),
            "deployment_note": (
                "Báo cáo dùng model fit 120 mẫu; model dự đoán được fit lại trên 150 mẫu, "
                "không đánh giá lại trên tập test cũ."
            ),
            "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
            "classification_report": classification_report(
                y_test,
                predictions,
                target_names=iris.target_names,
                output_dict=True,
                zero_division=0,
            ),
            "feature_min": X_train.min(axis=0).tolist(),
            "feature_max": X_train.max(axis=0).tolist(),
        }
        (folder / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"{key}: test={report['test_accuracy']:.4f}; "
            f"CV={cv_scores.mean():.4f} ± {cv_scores.std():.4f}"
        )


if __name__ == "__main__":
    train_all()
