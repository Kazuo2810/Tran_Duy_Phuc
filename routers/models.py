"""Router: models — các endpoint cùng nhóm chức năng."""
from fastapi import APIRouter
from common import *

router = APIRouter()

@router.get('/health', tags=['Hệ thống'], summary='Kiểm tra trạng thái hệ thống')
def health():
    ok=True
    try:
        with db.engine.connect() as con: con.execute(text('SELECT 1'))
    except SQLAlchemyError: ok=False
    return Response(json.dumps({'status':'ok' if ok and len(MODELS)==5 else 'degraded','database':ok,'models':list(MODELS)}),media_type='application/json',status_code=200 if ok and len(MODELS)==5 else 503)


@router.get('/api/models', tags=['Mô hình và đánh giá'], summary='Danh sách mô hình')
def models():
    return [{'model':k,'name':v,'available':k in MODELS,'report':REPORTS.get(k)} for k,v in MODEL_NAMES.items()]


@router.get('/api/models/{model}/evaluate', tags=['Mô hình và đánh giá'], summary='Kết quả đánh giá mô hình')
def evaluate(model:str):
    require_model(model); return REPORTS[model]


@router.get('/api/data', tags=['Dữ liệu'], summary='Xem dữ liệu Iris')
def dataset():
    iris=load_iris()
    return {'features':FEATURES,'labels':LABELS,'classes':iris.target_names.tolist(),'data':iris.data.tolist(),'target':iris.target.tolist(),'min':iris.data.min(axis=0).tolist(),'max':iris.data.max(axis=0).tolist()}


@router.get('/api/data/sample.csv', tags=['Dữ liệu'], summary='Tải file dữ liệu mẫu CSV')
def download_sample_data():
    """Tải bộ dữ liệu Iris gốc gồm 150 mẫu; không cần đăng nhập."""
    iris = load_iris()
    buffer = StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow([*FEATURES, 'species'])
    for values, target in zip(iris.data, iris.target):
        writer.writerow([*[float(value) for value in values], str(iris.target_names[int(target)])])
    return Response(
        buffer.getvalue().encode('utf-8-sig'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="iris_du_lieu_mau.csv"'},
    )


@lru_cache(maxsize=80)
def cached_visual(model,kind,x,y):
    estimator=require_model(model)
    if kind=='decision': return decision(estimator,model,x,y)
    if kind=='tree': raise HTTPException(404,'Các mô hình hiện tại đều là SVM, không có biểu đồ cây.')
    if kind=='margin' and model=='SVM': return margin_image()
    raise HTTPException(404,'Model này không có kiểu hình được yêu cầu.')


@router.get('/api/models/{model}/visual/{kind}', tags=['Mô hình và đánh giá'], summary='Biểu đồ trực quan hóa')
def visual(model:str,kind:str,x:int=Query(2,ge=0,le=3),y:int=Query(3,ge=0,le=3)):
    if x==y: raise HTTPException(422,'Hai trục phải khác nhau.')
    return Response(cached_visual(model,kind,x,y),media_type='image/png')


@router.get('/api/models/{model}/importance', tags=['Mô hình và đánh giá'], summary='Mức độ quan trọng của đặc trưng')
def importance(model:str):
    m=require_model(model)
    return {'features':LABELS,'values':m.feature_importances_.tolist() if hasattr(m,'feature_importances_') else None}

