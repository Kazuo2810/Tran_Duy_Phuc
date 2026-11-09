"""Router: predictions — các endpoint cùng nhóm chức năng."""
from fastapi import APIRouter
from common import *

router = APIRouter()

class PredictionInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    sepal_length: float=Field(gt=0,allow_inf_nan=False)
    sepal_width: float=Field(gt=0,allow_inf_nan=False)
    petal_length: float=Field(gt=0,allow_inf_nan=False)
    petal_width: float=Field(gt=0,allow_inf_nan=False)


def sign_result(row,owner):
    raw=json.dumps({'row':row,'owner':owner,'expires':time.time()+3600},ensure_ascii=False).encode()
    encoded=base64.urlsafe_b64encode(raw).decode()
    return encoded+'.'+hmac.new(SECRET,encoded.encode(),hashlib.sha256).hexdigest()


def verify_result(token,owner):
    try:
        encoded,sig=token.rsplit('.',1)
        if not hmac.compare_digest(sig,hmac.new(SECRET,encoded.encode(),hashlib.sha256).hexdigest()): raise ValueError()
        data=json.loads(base64.urlsafe_b64decode(encoded))
        if data['owner']!=owner or data['expires']<time.time(): raise ValueError()
        return data['row']
    except Exception: raise HTTPException(400,'Phiếu xuất kết quả không hợp lệ hoặc đã hết hạn (1 giờ).')


def persist_log(model,row):
    with db.engine.begin() as con: con.execute(insert(db.logs[model]).values(**row))


@router.post('/api/models/{model}/predict', tags=['Dự đoán'], summary='Dự đoán một mẫu Iris')
def predict(model:str,data:PredictionInput,user=Depends(session)):
    estimator=require_model(model); values=[getattr(data,k) for k in FEATURES]
    start=time.perf_counter(); result=str(load_iris().target_names[int(estimator.predict([values])[0])])
    row=dict(id=str(uuid.uuid4()),owner=user['owner'],time=datetime.now(timezone.utc).isoformat(),user=user['name'],model=model,version=REPORTS[model]['version'],result=result,elapsed_ms=round((time.perf_counter()-start)*1000,3),**data.model_dump())
    saved=True
    try: persist_log(model,row)
    except SQLAlchemyError:
        saved=False; logging.exception('Dự đoán thành công nhưng ghi log thất bại')
    public=public_log(row)
    report=REPORTS[model]
    warnings=[f'{LABELS[i]} nằm ngoài phạm vi tập train ({report["feature_min"][i]}–{report["feature_max"][i]} cm).' for i,v in enumerate(values) if v<report['feature_min'][i] or v>report['feature_max'][i]]
    return {**public,'prediction':result,'saved':saved,'message':'Đã lưu vào SQL.' if saved else 'Dự đoán thành công nhưng chưa lưu được SQL. Bạn vẫn có thể xuất kết quả hiện tại.', 'warnings':warnings,'export_token':sign_result({**public,'saved':saved},user['owner'])}


class BatchFileInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=7_000_000)


def parse_batch_file(data):
    try:
        raw = base64.b64decode(data.content_base64, validate=True)
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError('File tối đa 5 MB.')
        suffix = Path(data.filename).suffix.lower()
        if suffix == '.csv':
            reader = csv.reader(StringIO(raw.decode('utf-8-sig')))
            headers = next(reader, [])
            records = list(reader)
        elif suffix == '.xlsx':
            # Giới hạn kích thước giải nén trước khi đọc workbook.
            import zipfile
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                if sum(info.file_size for info in archive.infolist()) > 25 * 1024 * 1024:
                    raise ValueError('File Excel có dữ liệu giải nén quá lớn.')
            book = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            try:
                sheet = book.worksheets[0]
                if sheet.max_row and sheet.max_row > 10001:
                    raise ValueError('File Excel có quá nhiều dòng.')
                rows = sheet.iter_rows(values_only=True)
                headers = list(next(rows, []))
                records = list(rows)
            finally:
                book.close()
        elif suffix == '.json':
            records = json.loads(raw.decode('utf-8-sig'))
            if isinstance(records, dict):
                records = [records]
            if not isinstance(records, list):
                raise ValueError('JSON phải là danh sách đối tượng chứa 4 số đo.')
            headers = None
        else:
            raise ValueError('Chỉ hỗ trợ .csv, .xlsx và .json.')
        if headers is not None:
            headers = [str(h or '').strip().lower() for h in headers]
            if any(headers.count(f) != 1 for f in FEATURES):
                raise ValueError('Cần đúng một cột cho mỗi tên: ' + ', '.join(FEATURES))
            columns = {f: headers.index(f) for f in FEATURES}
            records = [(i, {f: row[col] if col < len(row) else None for f, col in columns.items()})
                       for i, row in enumerate(records, 2) if any(v is not None and str(v).strip() for v in row)]
        else:
            records = list(enumerate(records, 1))
        if not 1 <= len(records) <= 1000:
            raise ValueError('File phải có từ 1 đến 1000 mẫu.')
        parsed = []
        for line, row in records:
            try:
                if not isinstance(row, dict):
                    raise ValueError()
                values = {f: row.get(f) for f in FEATURES}
                if any(isinstance(v, bool) for v in values.values()):
                    raise ValueError()
                parsed.append((line, PredictionInput(**values)))
            except Exception:
                raise ValueError(f'Dòng {line}: cần đủ 4 số đo dạng số, hữu hạn và lớn hơn 0. Chưa dự đoán hoặc lưu dòng nào.')
        return parsed
    except HTTPException:
        raise
    except Exception as exc:
        detail = str(exc) if isinstance(exc, ValueError) else 'Không đọc được file. Kiểm tra định dạng, mã hóa UTF-8 và nội dung.'
        raise HTTPException(422, detail)


@router.post('/api/models/{model}/predict-batch', tags=['Dự đoán'], summary='Dự đoán hàng loạt từ file')
def predict_batch(model: str, data: BatchFileInput, user=Depends(session)):
    estimator = require_model(model)
    parsed = parse_batch_file(data)
    values = [[getattr(item, f) for f in FEATURES] for _, item in parsed]
    started = time.perf_counter()
    predictions = estimator.predict(values)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    class_names = load_iris().target_names
    now = datetime.now(timezone.utc).isoformat()
    rows = [dict(id=str(uuid.uuid4()), owner=user['owner'], time=now,
                 user=user['name'], model=model, version=REPORTS[model]['version'],
                 result=str(class_names[int(predictions[i])]),
                 elapsed_ms=round(elapsed_ms / len(parsed), 3), **item.model_dump())
            for i, (_, item) in enumerate(parsed)]
    saved = True
    try:
        with db.engine.begin() as con:
            con.execute(insert(db.logs[model]), rows)
    except SQLAlchemyError:
        saved = False
        logging.exception('Dự đoán hàng loạt thành công nhưng chưa lưu SQL')
    return {'model': model, 'count': len(rows), 'elapsed_ms': elapsed_ms,
            'saved': saved,
            'message': 'Đã lưu toàn bộ kết quả vào SQL.' if saved else 'Dự đoán thành công nhưng chưa lưu SQL. Hãy tải kết quả để giữ dữ liệu.',
            'items': [{**public_log(row),
                       'source_row': parsed[i][0]} for i, row in enumerate(rows)]}

