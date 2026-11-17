"""Module tạo biểu đồ trực quan hóa mô hình học máy dưới dạng ảnh PNG.

Lưu ý kỹ thuật:
- Sử dụng backend 'Agg' của Matplotlib để vẽ biểu đồ trên server không có màn hình (headless).
- Sử dụng threading.Lock() vì Matplotlib không an toàn đa luồng (thread-safe) khi vẽ đồng thời.
- Tách bạch rõ ràng giữa biểu đồ lát cắt 2D của mô hình 4 chiều thật và hình minh họa margin 2 chiều.
"""
from io import BytesIO
from functools import lru_cache
from threading import Lock
import matplotlib
matplotlib.use('Agg')  # Bắt buộc dùng backend không giao diện đồ họa trên server
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
import numpy as np
from sklearn.datasets import load_iris
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import plot_tree

from train import LABELS

LOCK = Lock()  # Khóa đồng bộ luồng khi gọi matplotlib
COLORS = ['#0ea5e9', '#f59e0b', '#8b5cf6']  # Bảng màu 3 lớp: Xanh dương, Cam, Tím


def png(fig) -> bytes:
    """Xuất đối tượng Figure của Matplotlib thành dữ liệu nhị phân PNG và giải phóng RAM."""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)  # Đóng figure ngay để tránh rò rỉ bộ nhớ (memory leak)
    return buf.getvalue()


def decision(model, key: str, a: int = 2, b: int = 3) -> bytes:
    """Vẽ lát cắt ranh giới quyết định (Decision Boundary) 2D của mô hình SVM 4 đặc trưng.

    Tham số:
        model: Pipeline mô hình đã huấn luyện (StandardScaler + SVC).
        key: Mã mô hình (ví dụ: 'SVM', 'SVM_RBF').
        a, b: Chỉ số 2 đặc trưng làm trục hoành và trục tung (mặc định 2 và 3 là kích thước cánh hoa).
              Hai đặc trưng còn lại được cố định tại giá trị trung vị (median).
    """
    iris = load_iris()
    X, y = iris.data, iris.target
    with LOCK:
        fig, ax = plt.subplots(figsize=(9, 5))

        # Tạo lưới tọa độ 160x160 phủ kín miền giá trị của 2 đặc trưng được chọn
        xx, yy = np.meshgrid(
            np.linspace(X[:, a].min() - .4, X[:, a].max() + .4, 160),
            np.linspace(X[:, b].min() - .3, X[:, b].max() + .3, 160),
        )
        # Khởi tạo mảng 4 chiều với giá trị trung vị, sau đó thay thế 2 cột (a, b) bằng tọa độ lưới
        grid = np.tile(np.median(X, axis=0), (xx.size, 1))
        grid[:, a], grid[:, b] = xx.ravel(), yy.ravel()

        # Dự đoán nhãn trên toàn bộ lưới điểm để tô màu vùng quyết định
        z = model.predict(grid).reshape(xx.shape)
        ax.contourf(xx, yy, z, levels=[-.5, .5, 1.5, 2.5], colors=COLORS, alpha=.18)

        # Vẽ các điểm dữ liệu thực tế của 3 loài hoa Iris
        for i, name in enumerate(iris.target_names):
            ax.scatter(
                X[y == i, a], X[y == i, b],
                s=23, color=COLORS[i], label=name, edgecolors='white', linewidths=.4,
            )

        # Chiếu ngược các Support Vectors từ không gian đã chuẩn hóa về đơn vị cm gốc để khoanh tròn
        if key.startswith('SVM') and hasattr(model[-1], 'support_vectors_'):
            sv = model[0].inverse_transform(model[-1].support_vectors_)
            ax.scatter(
                sv[:, a], sv[:, b],
                s=70, facecolors='none', edgecolors='#111827', linewidths=1,
                label='Support vectors (chiếu từ 4D)',
            )

        fixed = ', '.join(f'{LABELS[i]}={np.median(X[:, i]):.2f} cm' for i in range(4) if i not in (a, b))
        ax.set(
            title=f'{key}: lát cắt SVM triển khai với 4 đặc trưng',
            xlabel=LABELS[a] + ' (cm)',
            ylabel=LABELS[b] + ' (cm)',
        )
        ax.legend(loc='best', fontsize=8)
        fig.text(
            .05, -.02,
            fixed + '\nCác điểm Iris là phép chiếu 4D; không nhất thiết khớp màu nền của lát cắt.',
            fontsize=9,
        )
        return png(fig)


def tree_image(model, key: str) -> bytes:
    """Vẽ cấu trúc cây quyết định (dành cho Decision Tree hoặc cây đầu tiên của Random Forest)."""
    with LOCK:
        fig, ax = plt.subplots(figsize=(19, 9))
        tree = model if key == 'DT' else model.estimators_[0]
        plot_tree(
            tree,
            feature_names=LABELS,
            class_names=['setosa', 'versicolor', 'virginica'],
            filled=True,
            max_depth=None if key == 'DT' else 3,
            fontsize=8,
            ax=ax,
        )
        ax.set_title(
            'Cây Decision Tree triển khai'
            if key == 'DT'
            else 'Random Forest: cây số 1, chỉ hiển thị đến độ sâu 3'
        )
        return png(fig)


def margin_image() -> bytes:
    """Vẽ biểu đồ minh họa khái niệm Siêu phẳng phân tách (f=0) và Lề (Margin f=±1) của SVM.

    Lưu ý: Chỉ dùng 2 lớp đầu (setosa, versicolor) và 2 đặc trưng cánh hoa để minh họa trực quan
    bài toán phân lớp nhị phân tuyến tính.
    """
    with LOCK:
        iris = load_iris()
        X = iris.data[iris.target < 2, 2:4]
        y = iris.target[iris.target < 2]

        m = make_pipeline(StandardScaler(), SVC(kernel='linear', C=1.0)).fit(X, y)
        xx, yy = np.meshgrid(np.linspace(.7, 5.5, 180), np.linspace(0, 2, 180))
        scores = m.decision_function(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.scatter(X[:, 0], X[:, 1], c=y, cmap=ListedColormap(COLORS[:2]), s=25)

        # Vẽ 3 đường đồng mức tại giá trị hàm quyết định: -1 (lề âm), 0 (siêu phẳng), +1 (lề dương)
        lines = ax.contour(xx, yy, scores, levels=[-1, 0, 1], colors='black', linestyles=['--', '-', '--'])
        ax.clabel(lines, inline=True, fmt={-1: 'f=-1', 0: 'f=0', 1: 'f=1'})

        # Đánh dấu các điểm nằm trên hoặc vi phạm biên lề (Support Vectors)
        sv = m[0].inverse_transform(m[-1].support_vectors_)
        ax.scatter(sv[:, 0], sv[:, 1], s=90, facecolors='none', edgecolors='black', label='Support vectors')

        ax.legend(
            handles=[
                Line2D([], [], marker='o', linestyle='', color=COLORS[0], label='setosa'),
                Line2D([], [], marker='o', linestyle='', color=COLORS[1], label='versicolor'),
                Line2D([], [], color='black', label='f=0; nét đứt: f=±1'),
            ],
            fontsize=8,
        )
        ax.set(
            title='Minh họa riêng: SVM nhị phân, 2 đặc trưng, C=1',
            xlabel=LABELS[2] + ' (cm)',
            ylabel=LABELS[3] + ' (cm)',
        )
        fig.text(
            .04, -.02,
            'Đây là model minh họa riêng, không phải model dự đoán Iris 3 lớp / 4 đặc trưng.',
            fontsize=9,
        )
        return png(fig)
