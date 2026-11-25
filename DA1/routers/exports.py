"""
Router: exports — Xuất dữ liệu lịch sử hoặc kết quả dự đoán ra file Microsoft Excel (.xlsx).
Sử dụng thư viện `openpyxl` để tạo workbook nhiều sheet, định dạng bảng và tự động căn chỉnh độ rộng cột.
"""
from fastapi import APIRouter
from common import *

router = APIRouter()

# Danh sách tiêu đề cột cho các sheet chi tiết của từng mô hình
HEADERS = [
    'ID', 'Ngày giờ Việt Nam', 'Người thực hiện', 'Mô hình', 'Phiên bản',
    'Dài đài (cm)', 'Rộng đài (cm)', 'Dài cánh (cm)', 'Rộng cánh (cm)',
    'Kết quả', 'Xử lý (ms)', 'Trạng thái lưu SQL'
]


def style_sheet(ws):
    """
    Định dạng giao diện chuẩn cho một worksheet Excel:
    - Cố định dòng tiêu đề đầu tiên (Freeze Panes) và bật bộ lọc (Auto Filter).
    - Tô màu nền xanh cyan và in đậm chữ cho dòng tiêu đề.
    - Tự động tính toán và điều chỉnh độ rộng từng cột dựa trên nội dung dài nhất.
    """
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='0891B2')
    for col in ws.columns:
        width = min(42, max(14, max(len(str(c.value or '')) for c in col) + 2))
        ws.column_dimensions[col[0].column_letter].width = width


def excel_response(rows):
    """
    Tạo file Excel hoàn chỉnh trong bộ nhớ (BytesIO) từ danh sách các bản ghi dự đoán:
    1. Sheet 'Tổng hợp': Thống kê số lượng bản ghi và các chỉ số đánh giá (Accuracy, F1, CV) của từng mô hình.
    2. Các sheet riêng biệt theo tên mô hình (VD: SVM, RF...): Chứa dữ liệu chi tiết từng lần dự đoán.
    3. Sheet 'Ghi chú': Giải thích múi giờ, nguồn dữ liệu và quyền truy cập.
    """
    book = Workbook()
    summary = book.active
    summary.title = 'Tổng hợp'
    summary.append(['Mô hình', 'Số bản ghi', 'Accuracy test', 'F1 macro', 'CV train trung bình'])

    for key in MODEL_NAMES:
        selected = [r for r in rows if r['model'] == key]
        if not selected:
            continue
        
        # Ghi thông số tổng hợp của mô hình vào sheet đầu tiên
        report = REPORTS.get(key, {})
        summary.append([key, len(selected), report.get('test_accuracy'), report.get('f1'), report.get('cv_accuracy')])
        for c in summary[summary.max_row][2:]:
            c.number_format = '0.00%'

        # Tạo sheet chi tiết cho từng mô hình có dữ liệu
        ws = book.create_sheet(key)
        ws.append(HEADERS)
        for r in selected:
            # Chuyển đổi thời gian từ UTC sang múi giờ Việt Nam (Asia/Ho_Chi_Minh)
            dt = datetime.fromisoformat(r['time']).astimezone(VN).replace(tzinfo=None)
            ws.append([
                r.get('id', ''), dt, r['user'], key, r['version'],
                *[r[f] for f in FEATURES],
                r['result'], r['elapsed_ms'],
                'Đã lưu' if r.get('saved', True) else 'Chưa lưu'
            ])
            ws.cell(ws.max_row, 2).number_format = 'dd/mm/yyyy hh:mm:ss'
            # Ép kiểu chuỗi (string) cho các cột ID, tên, phiên bản để tránh Excel tự định dạng sai
            for i in [1, 3, 4, 5, 10]:
                ws.cell(ws.max_row, i).data_type = 's'
        style_sheet(ws)

    summary.append(['Tổng cộng', len(rows)])
    style_sheet(summary)

    # Tạo sheet giải thích thông tin bổ sung
    note = book.create_sheet('Ghi chú')
    note.append(['Nội dung', 'Giải thích'])
    note.append(['Múi giờ', 'Asia/Ho_Chi_Minh; nguồn SQL lưu UTC.'])
    note.append(['Đánh giá', 'Các chỉ số tổng hợp là báo cáo hiện có; phiên bản của mỗi dự đoán nằm ở sheet chi tiết.'])
    note.append(['Quyền truy cập', 'Chỉ xuất dữ liệu thuộc tài khoản đang đăng nhập.'])
    style_sheet(note)

    # Xuất workbook ra luồng byte và trả về dưới dạng file tải xuống
    buf = BytesIO()
    book.save(buf)
    return Response(
        buf.getvalue(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="Iris_ket_qua.xlsx"'}
    )


@router.get('/api/export', tags=['Xuất Excel'], summary='Xuất lịch sử dự đoán')
def export(
    model: str | None = None,
    user: str | None = None,
    start: date | None = None,
    end: date | None = None,
    who=Depends(session)
):
    """Truy vấn lịch sử dự đoán của người dùng hiện tại theo bộ lọc và xuất ra file Excel."""
    rows = query_rows(who['owner'], model, user, start, end)
    if not rows:
        raise HTTPException(404, 'Không có bản ghi phù hợp để xuất.')
    return excel_response(rows)


class ExportInput(BaseModel):
    """Schema nhận token chứa dữ liệu kết quả dự đoán vừa thực hiện."""
    token: str = Field(max_length=12000)


@router.post('/api/export-current', tags=['Xuất Excel'], summary='Xuất kết quả dự đoán hiện tại')
def export_current(data: ExportInput, who=Depends(session)):
    """
    Xuất file Excel cho một kết quả dự đoán đơn lẻ ngay sau khi dự đoán 
    (hữu ích ngay cả khi việc lưu vào SQL bị lỗi) thông qua token đã ký HMAC.
    """
    return excel_response([verify_result(data.token, who['owner'])])
