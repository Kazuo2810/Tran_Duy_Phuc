"""Huấn luyện đúng quy trình trang 7–16 của da2.pdf."""
from pathlib import Path
import hashlib
import json
import platform
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
                            roc_auc_score, average_precision_score,
                            confusion_matrix, classification_report)

ROOT = Path(__file__).resolve().parents[1]
WARNING = 'Chỉ phục vụ học tập; kết quả không phải chẩn đoán y tế và không thay thế bác sĩ.'


def main():
    bundle = load_breast_cancer(as_frame=True)
    X, y = bundle.data, bundle.target
    assert list(bundle.target_names) == ['malignant', 'benign']
    assert X.shape == (569, 30) and not X.isna().any().any()
    assert np.isfinite(X.to_numpy()).all()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42)
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('svc', SVC(kernel='rbf', probability=True,
                    class_weight='balanced', random_state=42))])
    search = GridSearchCV(
        pipeline, {'svc__C': [0.1, 1, 10, 100],
                   'svc__gamma': ['scale', 0.001, 0.01, 0.1]},
        scoring='recall_macro',
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
        n_jobs=2, refit=True, return_train_score=True)
    search.fit(X_train, y_train)
    model = search.best_estimator_
    pred = model.predict(X_test)
    idx = list(model.classes_).index(0)
    prob = model.predict_proba(X_test)[:, idx]
    cm = confusion_matrix(y_test, pred, labels=[0, 1])
    metrics = {
        'accuracy': accuracy_score(y_test, pred),
        'sensitivity_malignant': recall_score(y_test, pred, pos_label=0),
        'specificity_benign': recall_score(y_test, pred, pos_label=1),
        'precision_malignant': precision_score(y_test, pred, pos_label=0),
        'f1_malignant': f1_score(y_test, pred, pos_label=0),
        'roc_auc_malignant': roc_auc_score((y_test == 0).astype(int), prob),
        'average_precision_malignant': average_precision_score((y_test == 0).astype(int), prob),
        'false_negative_malignant': int(cm[0, 1]),
        'confusion_matrix_labels_0_1': cm.tolist(),
        'train_recall_macro': recall_score(y_train, model.predict(X_train), average='macro'),
        'cv_recall_macro': float(search.best_score_),
        'test_recall_macro': recall_score(y_test, pred, average='macro'),
        'classification_report': classification_report(y_test, pred,
            labels=[0, 1], target_names=list(bundle.target_names), output_dict=True)}
    for folder in ('artifacts', 'reports'):
        (ROOT / folder).mkdir(exist_ok=True)
    path = ROOT / 'artifacts/breast_cancer_svm.joblib'
    joblib.dump(model, path)
    metadata = {
        'model_name': 'breast-cancer-svm-rbf', 'model_version': '1.0.0',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'feature_names': list(X.columns),
        'class_mapping': {'0': 'malignant', '1': 'benign'},
        'best_params': search.best_params_, 'sklearn_version': sklearn.__version__,
        'python_version': platform.python_version(), 'random_state': 42,
        'dataset': 'sklearn.datasets.load_breast_cancer (WDBC)',
        'train_size': len(X_train), 'test_size': len(X_test),
        'selection_metric': 'recall_macro', 'cv_folds': 5,
        'model_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'training_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'warning': WARNING,
        'input_domain': 'Số hữu hạn không âm; kiểm tra kỹ thuật, không xác nhận miền sinh học.',
        'metrics': metrics}
    def save(relative, value):
        (ROOT / relative).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    save('artifacts/metadata.json', metadata)
    save('reports/metrics.json', metrics)
    # Lấy ví dụ từ tập test; không dùng chúng để chọn mô hình.
    sample = {'features': {k: float(v) for k, v in X_test.iloc[0].items()}}
    save('sample_request.json', sample)
    fixtures = []
    for label in (0, 1):
        row = X_test[y_test == label].iloc[0]
        fixtures.append({'features': row.to_dict(), 'expected_class': int(model.predict(row.to_frame().T)[0])})
    save('tests/model_cases.json', fixtures)
    X.describe().T.to_csv(ROOT / 'reports/feature_statistics.csv')
    import pandas as pd
    pd.DataFrame(search.cv_results_).to_csv(ROOT / 'reports/cv_results.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay, PrecisionRecallDisplay
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    ConfusionMatrixDisplay(cm, display_labels=bundle.target_names).plot(ax=axes[0], colorbar=False)
    RocCurveDisplay.from_predictions((y_test == 0).astype(int), prob, ax=axes[1], name='Malignant')
    PrecisionRecallDisplay.from_predictions((y_test == 0).astype(int), prob, ax=axes[2], name='Malignant')
    fig.tight_layout()
    fig.savefig(ROOT / 'reports/evaluation.png', dpi=160)
    plt.close(fig)
    lines = ['# Kết quả thực nghiệm Dự án 2', '',
        'Sinh viên: Trần Duy Phúc – 24CKDL', '',
        f'Dữ liệu: 569 mẫu, 30 đặc trưng; train={len(X_train)}, test={len(X_test)}.',
        f'Tham số tốt nhất: {search.best_params_}.', '',
        '| Chỉ số | Giá trị |', '|---|---:|']
    lines += [f'| {k} | {v:.6f} |' for k, v in metrics.items() if isinstance(v, (int, float))]
    lines += ['', 'Ma trận nhầm lẫn (hàng: nhãn thật; cột: dự đoán; thứ tự ác tính, lành tính):',
        f'```text\n{cm}\n```', '',
        'FN ác tính là ô hàng 0, cột 1: ca ác tính bị dự đoán là lành tính.',
        'Average precision là cách tổng hợp đường precision–recall; không đồng nhất với tích phân hình thang PR-AUC.',
        'GridSearchCV tối ưu recall_macro đúng bài giảng, không trực tiếp tối ưu riêng sensitivity ác tính.',
        'Nhãn dùng SVC.predict; không tự thay bằng ngưỡng xác suất 0.5. Xác suất và nhãn có thể không đồng thuận.',
        'Mô hình lưu là mô hình refit trên 455 mẫu train; không huấn luyện lại trên test sau đánh giá.',
        'CV chỉ nằm trong train. Các điểm test không tham gia chuẩn hóa hay chọn tham số.',
        'Chưa hiệu chỉnh xác suất ngoại bộ, chưa lựa chọn ngưỡng trên validation và chưa kiểm định lâm sàng.',
        '', '![Đánh giá](evaluation.png)', '', WARNING]
    (ROOT / 'reports/KET_QUA.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'best_params': search.best_params_, 'metrics': metrics}, indent=2))


if __name__ == '__main__':
    main()
