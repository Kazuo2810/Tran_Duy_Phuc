"""Huấn luyện và đánh giá 4 biến thể SVM trên bộ dữ liệu WDBC."""
from pathlib import Path
import hashlib, json, platform
from datetime import datetime, timezone
import joblib
import numpy as np
import sklearn
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import (accuracy_score, recall_score, precision_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix, classification_report)

ROOT = Path(__file__).resolve().parents[1]
WARNING = "Chỉ phục vụ học tập; kết quả không phải chẩn đoán y tế và không thay thế bác sĩ."
MODEL_CONFIGS = {
    "SVM_LINEAR": {"name": "SVM Linear", "kernel": "linear",
        "grid": {"svc__C": [0.1, 1, 10, 100]}},
    "SVM_RBF": {"name": "SVM RBF", "kernel": "rbf",
        "grid": {"svc__C": [0.1, 1, 10, 100], "svc__gamma": ["scale", 0.001, 0.01, 0.1]}},
    "SVM_POLY": {"name": "SVM Polynomial", "kernel": "poly",
        "grid": {"svc__C": [0.1, 1, 10], "svc__degree": [2, 3, 4],
                 "svc__gamma": ["scale", 0.01], "svc__coef0": [0, 1]}},
    "SVM_SIGMOID": {"name": "SVM Sigmoid", "kernel": "sigmoid",
        "grid": {"svc__C": [0.1, 1, 10, 100], "svc__gamma": ["scale", 0.001, 0.01],
                 "svc__coef0": [0, 1]}},
}

def main():
    data = load_breast_cancer(as_frame=True)
    X, y = data.data, data.target
    assert X.shape == (569, 30) and not X.isna().any().any()
    assert np.isfinite(X.to_numpy()).all()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    (ROOT / "artifacts/models").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports/models").mkdir(parents=True, exist_ok=True)
    all_reports = {}
    for key, cfg in MODEL_CONFIGS.items():
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("svc", SVC(kernel=cfg["kernel"], probability=False,
                        class_weight="balanced", random_state=42))
        ])
        search = GridSearchCV(pipe, cfg["grid"], scoring="recall_macro",
            cv=cv, n_jobs=1, refit=True, return_train_score=True)
        search.fit(X_train, y_train)
        best_params = {k.replace("svc__", ""): v for k, v in search.best_params_.items()}
        evaluation_model = Pipeline([
            ("scaler", StandardScaler()),
            ("svc", SVC(kernel=cfg["kernel"], probability=True,
                        class_weight="balanced", random_state=42, **best_params))
        ]).fit(X_train, y_train)
        pred = evaluation_model.predict(X_test)
        malignant_idx = list(evaluation_model.classes_).index(0)
        prob = evaluation_model.predict_proba(X_test)[:, malignant_idx]
        cm = confusion_matrix(y_test, pred, labels=[0, 1])
        metrics = {
            "accuracy": float(accuracy_score(y_test, pred)),
            "sensitivity_malignant": float(recall_score(y_test, pred, pos_label=0)),
            "specificity_benign": float(recall_score(y_test, pred, pos_label=1)),
            "precision_malignant": float(precision_score(y_test, pred, pos_label=0, zero_division=0)),
            "f1_malignant": float(f1_score(y_test, pred, pos_label=0, zero_division=0)),
            "roc_auc_malignant": float(roc_auc_score((y_test == 0).astype(int), prob)),
            "average_precision_malignant": float(average_precision_score((y_test == 0).astype(int), prob)),
            "false_negative_malignant": int(cm[0, 1]),
            "confusion_matrix_labels_0_1": cm.tolist(),
            "train_recall_macro": float(recall_score(y_train, evaluation_model.predict(X_train), average="macro")),
            "cv_recall_macro": float(search.best_score_),
            "test_recall_macro": float(recall_score(y_test, pred, average="macro")),
            "classification_report": classification_report(y_test, pred, labels=[0, 1],
                target_names=list(data.target_names), output_dict=True, zero_division=0),
        }
        folder = ROOT / "artifacts/models" / key
        folder.mkdir(parents=True, exist_ok=True)
        evaluation_path = folder / "evaluation.joblib"
        deployment_path = folder / "deployment.joblib"
        joblib.dump(evaluation_model, evaluation_path)
        deployment_model = Pipeline([
            ("scaler", StandardScaler()),
            ("svc", SVC(kernel=cfg["kernel"], probability=True,
                        class_weight="balanced", random_state=42, **best_params)
        ]).fit(X, y)
        joblib.dump(deployment_model, deployment_path)
        report = {
            "model_key": key, "model_name": cfg["name"], "kernel": cfg["kernel"],
            "model_version": hashlib.sha256(deployment_path.read_bytes()).hexdigest()[:12],
            "sklearn_version": sklearn.__version__, "python_version": platform.python_version(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset": "sklearn.datasets.load_breast_cancer (WDBC)",
            "feature_names": list(X.columns),
            "class_mapping": {"0": "malignant", "1": "benign"},
            "train_size": len(X_train), "test_size": len(X_test),
            "selection_metric": "recall_macro", "cv_folds": 5,
            "best_params": search.best_params_, "metrics": metrics,
            "evaluation_artifact": f"artifacts/models/{key}/evaluation.joblib",
            "deployment_artifact": f"artifacts/models/{key}/deployment.joblib",
            "evaluation_sha256": hashlib.sha256(evaluation_path.read_bytes()).hexdigest(),
            "deployment_sha256": hashlib.sha256(deployment_path.read_bytes()).hexdigest(),
            "warning": WARNING,
        }
        (folder / "metadata.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (ROOT / "reports/models" / f"{key.lower()}_metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        all_reports[key] = report
        print(f"{cfg['name']}: accuracy={metrics['accuracy']:.4f}; "
              f"sensitivity={metrics['sensitivity_malignant']:.4f}; "
              f"CV recall_macro={metrics['cv_recall_macro']:.4f}")
    default_key = "SVM_RBF"
    default = all_reports[default_key]
    metadata = {
        "model_name": "WDBC – 4 biến thể SVM", "model_version": "2.0.0",
        "default_model": default_key, "models": all_reports,
        "feature_names": list(X.columns),
        "class_mapping": {"0": "malignant", "1": "benign"},
        "dataset": "sklearn.datasets.load_breast_cancer (WDBC)",
        "sklearn_version": sklearn.__version__, "python_version": platform.python_version(),
        "warning": WARNING, "metrics": default["metrics"],
        "best_params": default["best_params"],
    }
    (ROOT / "artifacts/metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    # Giữ artifact RBF cũ để tương thích các script/đường dẫn phiên bản trước.
    joblib.dump(joblib.load(ROOT / "artifacts/models/SVM_RBF/deployment.joblib"),
                ROOT / "artifacts/breast_cancer_svm.joblib")
    print("Hoàn tất 4 mô hình SVM:", ", ".join(MODEL_CONFIGS))

if __name__ == "__main__":
    main()
