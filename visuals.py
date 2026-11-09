"""Trực quan model thật; tách riêng hình SVM nhị phân minh họa margin."""
from io import BytesIO
from functools import lru_cache
from threading import Lock
import matplotlib
matplotlib.use('Agg')
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
LOCK = Lock()
COLORS = ['#0ea5e9', '#f59e0b', '#8b5cf6']

def png(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    return buf.getvalue()

def decision(model, key, a=2, b=3):
    iris = load_iris(); X, y = iris.data, iris.target
    with LOCK:
        fig, ax = plt.subplots(figsize=(9, 5))
        xx, yy = np.meshgrid(np.linspace(X[:,a].min()-.4, X[:,a].max()+.4, 160), np.linspace(X[:,b].min()-.3, X[:,b].max()+.3, 160))
        grid = np.tile(np.median(X, axis=0), (xx.size,1))
        grid[:,a], grid[:,b] = xx.ravel(), yy.ravel()
        z = model.predict(grid).reshape(xx.shape)
        ax.contourf(xx, yy, z, levels=[-.5,.5,1.5,2.5], colors=COLORS, alpha=.18)
        for i, name in enumerate(iris.target_names):
            ax.scatter(X[y==i,a], X[y==i,b], s=23, color=COLORS[i], label=name, edgecolors='white', linewidths=.4)
        if key.startswith('SVM') and hasattr(model[-1], 'support_vectors_'):
            sv = model[0].inverse_transform(model[-1].support_vectors_)
            ax.scatter(sv[:,a], sv[:,b], s=70, facecolors='none', edgecolors='#111827', linewidths=1, label='Support vectors (chiếu từ 4D)')
        fixed = ', '.join(f'{LABELS[i]}={np.median(X[:,i]):.2f} cm' for i in range(4) if i not in (a,b))
        ax.set(title=f'{key}: lát cắt SVM triển khai với 4 đặc trưng', xlabel=LABELS[a]+' (cm)', ylabel=LABELS[b]+' (cm)')
        ax.legend(loc='best', fontsize=8)
        fig.text(.05, -.02, fixed+'\nCác điểm Iris là phép chiếu 4D; không nhất thiết khớp màu nền của lát cắt.', fontsize=9)
        return png(fig)

def tree_image(model, key):
    with LOCK:
        fig, ax = plt.subplots(figsize=(19, 9))
        tree = model if key == 'DT' else model.estimators_[0]
        plot_tree(tree, feature_names=LABELS, class_names=['setosa','versicolor','virginica'], filled=True, max_depth=None if key=='DT' else 3, fontsize=8, ax=ax)
        ax.set_title('Cây Decision Tree triển khai' if key=='DT' else 'Random Forest: cây số 1, chỉ hiển thị đến độ sâu 3')
        return png(fig)

def margin_image():
    with LOCK:
        iris=load_iris(); X=iris.data[iris.target<2,2:4]; y=iris.target[iris.target<2]
        m=make_pipeline(StandardScaler(), SVC(kernel='linear', C=1.0)).fit(X,y)
        xx,yy=np.meshgrid(np.linspace(.7,5.5,180),np.linspace(0,2,180))
        scores=m.decision_function(np.c_[xx.ravel(),yy.ravel()]).reshape(xx.shape)
        fig,ax=plt.subplots(figsize=(9,5))
        ax.scatter(X[:,0],X[:,1],c=y,cmap=ListedColormap(COLORS[:2]),s=25)
        lines=ax.contour(xx,yy,scores,levels=[-1,0,1],colors='black',linestyles=['--','-','--'])
        ax.clabel(lines,inline=True,fmt={-1:'f=-1',0:'f=0',1:'f=1'})
        sv=m[0].inverse_transform(m[-1].support_vectors_)
        ax.scatter(sv[:,0],sv[:,1],s=90,facecolors='none',edgecolors='black',label='Support vectors')
        ax.legend(handles=[Line2D([],[],marker='o',linestyle='',color=COLORS[0],label='setosa'),Line2D([],[],marker='o',linestyle='',color=COLORS[1],label='versicolor'),Line2D([],[],color='black',label='f=0; nét đứt: f=±1')],fontsize=8)
        ax.set(title='Minh họa riêng: SVM nhị phân, 2 đặc trưng, C=1',xlabel=LABELS[2]+' (cm)',ylabel=LABELS[3]+' (cm)')
        fig.text(.04,-.02,'Đây là model minh họa riêng, không phải model dự đoán Iris 3 lớp / 4 đặc trưng.',fontsize=9)
        return png(fig)
