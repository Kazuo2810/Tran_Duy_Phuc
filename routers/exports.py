"""Router: exports — các endpoint cùng nhóm chức năng."""
from fastapi import APIRouter
from common import *

router = APIRouter()

HEADERS=['ID','Ngày giờ Việt Nam','Người thực hiện','Mô hình','Phiên bản','Dài đài (cm)','Rộng đài (cm)','Dài cánh (cm)','Rộng cánh (cm)','Kết quả','Xử lý (ms)','Trạng thái lưu SQL']


def style_sheet(ws):
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    for cell in ws[1]: cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='0891B2')
    for col in ws.columns:
        width=min(42,max(14,max(len(str(c.value or '')) for c in col)+2))
        ws.column_dimensions[col[0].column_letter].width=width


def excel_response(rows):
    book=Workbook(); summary=book.active; summary.title='Tổng hợp'
    summary.append(['Mô hình','Số bản ghi','Accuracy test','F1 macro','CV train trung bình'])
    for key in MODEL_NAMES:
        selected=[r for r in rows if r['model']==key]
        if not selected: continue
        report=REPORTS.get(key,{})
        summary.append([key,len(selected),report.get('test_accuracy'),report.get('f1'),report.get('cv_accuracy')])
        for c in summary[summary.max_row][2:]: c.number_format='0.00%'
        ws=book.create_sheet(key); ws.append(HEADERS)
        for r in selected:
            dt=datetime.fromisoformat(r['time']).astimezone(VN).replace(tzinfo=None)
            ws.append([r.get('id',''),dt,r['user'],key,r['version'],*[r[f] for f in FEATURES],r['result'],r['elapsed_ms'],'Đã lưu' if r.get('saved',True) else 'Chưa lưu'])
            ws.cell(ws.max_row,2).number_format='dd/mm/yyyy hh:mm:ss'
            for i in [1,3,4,5,10]: ws.cell(ws.max_row,i).data_type='s'
        style_sheet(ws)
    summary.append(['Tổng cộng',len(rows)])
    style_sheet(summary)
    note=book.create_sheet('Ghi chú'); note.append(['Nội dung','Giải thích'])
    note.append(['Múi giờ','Asia/Ho_Chi_Minh; nguồn SQL lưu UTC.'])
    note.append(['Đánh giá','Các chỉ số tổng hợp là báo cáo hiện có; phiên bản của mỗi dự đoán nằm ở sheet chi tiết.'])
    note.append(['Quyền truy cập','Chỉ xuất dữ liệu thuộc tài khoản đang đăng nhập.'])
    style_sheet(note)
    buf=BytesIO(); book.save(buf)
    return Response(buf.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="Iris_ket_qua.xlsx"'})


@router.get('/api/export', tags=['Xuất Excel'], summary='Xuất lịch sử dự đoán')
def export(model:str|None=None,user:str|None=None,start:date|None=None,end:date|None=None,who=Depends(session)):
    rows=query_rows(who['owner'],model,user,start,end)
    if not rows: raise HTTPException(404,'Không có bản ghi phù hợp để xuất.')
    return excel_response(rows)


class ExportInput(BaseModel):
    token:str=Field(max_length=12000)


@router.post('/api/export-current', tags=['Xuất Excel'], summary='Xuất kết quả dự đoán hiện tại')
def export_current(data:ExportInput,who=Depends(session)):
    return excel_response([verify_result(data.token,who['owner'])])

