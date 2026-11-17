"""Quản lý kết nối cơ sở dữ liệu SQLAlchemy và khai báo lược đồ (Schema) các bảng.

Hỗ trợ đa hệ quản trị cơ sở dữ liệu (Database Agnostic):
1. PostgreSQL: Tự động chuẩn hóa prefix 'postgres://' thành 'postgresql+psycopg://' (dùng trên Render).
2. SQL Server: Tự động cấu hình ODBC Driver 18 nếu khai báo biến SQLSERVER_SERVER ở môi trường Windows.
3. SQLite: Mặc định tạo file 'iris.db' cục bộ nếu không có cấu hình server ngoài.
"""
import os
from pathlib import Path
from sqlalchemy.engine import URL
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Unicode,
    Boolean,
    inspect,
    text,
    update,
    Float,
    ForeignKey,
)

from train import MODEL_NAMES


ROOT = Path(__file__).resolve().parent

# --- 1. XÁC ĐỊNH CHUỖI KẾT NỐI CƠ SỞ DỮ LIỆU ---
database_url = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{ROOT / 'iris.db'}",
)

# Chuẩn hóa driver psycopg (v3) cho PostgreSQL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options = {"pool_pre_ping": True}  # Tự động kiểm tra kết nối sống trước khi truy vấn

if database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

# Tùy chọn kết nối SQL Server nội bộ (chỉ kích hoạt khi chạy local không qua Render)
sqlserver_server = os.getenv("SQLSERVER_SERVER", "").strip()
if sqlserver_server and not os.getenv("RENDER") and not os.getenv("DATABASE_URL"):
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={sqlserver_server};"
        f"DATABASE={os.getenv('SQLSERVER_DATABASE', 'IrisML')};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )
    database_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine_options = {"pool_pre_ping": True}  # Bỏ tùy chọn check_same_thread chỉ dành cho SQLite

engine = create_engine(database_url, **engine_options)
admin_default = "0" if engine.dialect.name == "mssql" else "false"
metadata = MetaData()


# --- 2. KHAI BÁO CÁC BẢNG DỮ LIỆU ---
# Bảng lưu trữ phiên cũ (giữ lại để tương thích ngược, tránh mất dữ liệu lịch sử cũ)
sessions = Table(
    "iris_sessions",
    metadata,
    Column("owner", String(64), primary_key=True),
    Column("name", Unicode(80), nullable=False),
)

# Bảng tài khoản người dùng (mật khẩu được băm bằng Argon2)
users = Table(
    "iris_users",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("username", String(80), nullable=False, unique=True, index=True),
    Column("name", Unicode(80), nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("is_admin", Boolean, nullable=False, default=False, server_default=text(admin_default)),
)

# Bảng lưu bản băm token phiên đăng nhập cũ
auth_sessions = Table(
    "iris_auth_sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", String(36), ForeignKey("iris_users.id"), nullable=False, index=True),
    Column("created_at", String(40), nullable=False),
    Column("expires_at", Float, nullable=False),
)

# Tạo 5 bảng log riêng biệt cho 5 cấu hình mô hình SVM:
# logs_svm, logs_svm_rbf, logs_svm_poly, logs_svm_sig, logs_svm_opt
logs = {}
for model in MODEL_NAMES:
    logs[model] = Table(
        f"logs_{model.lower()}",
        metadata,
        Column("id", String(36), primary_key=True),            # UUID của bản ghi dự đoán
        Column("owner", String(64), nullable=False, index=True), # UUID người dùng thực hiện
        Column("time", String(40), nullable=False, index=True),  # Thời gian dự đoán (UTC ISO)
        Column("user", Unicode(80), nullable=False),             # Tên người thực hiện tại thời điểm dự đoán
        Column("model", String(8), nullable=False),              # Mã cấu hình SVM (tối đa 8 ký tự)
        Column("version", String(32), nullable=False),           # Mã băm phiên bản file mô hình
        Column("sepal_length", Float, nullable=False),           # Chiều dài đài hoa (cm)
        Column("sepal_width", Float, nullable=False),            # Chiều rộng đài hoa (cm)
        Column("petal_length", Float, nullable=False),           # Chiều dài cánh hoa (cm)
        Column("petal_width", Float, nullable=False),            # Chiều rộng cánh hoa (cm)
        Column("result", String(40), nullable=False),            # Tên loài hoa Iris dự đoán được
        Column("elapsed_ms", Float, nullable=False),             # Thời gian suy luận của mô hình (mili-giây)
    )


# --- 3. KHỞI TẠO & DI TRÚ CẤU TRÚC BẢNG (MIGRATION) ---
def init_db():
    """Khởi tạo toàn bộ bảng và tự động bổ sung cột 'is_admin' nếu nâng cấp từ DB cũ."""
    with engine.begin() as con:
        inspector = inspect(con)
        if inspector.has_table("iris_users"):
            columns = {column["name"] for column in inspector.get_columns("iris_users")}
            if "is_admin" not in columns:
                if engine.dialect.name == "mssql":
                    sql = "ALTER TABLE iris_users ADD is_admin BIT NOT NULL DEFAULT 0"
                else:
                    sql = "ALTER TABLE iris_users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"
                con.execute(text(sql))

    metadata.create_all(engine)

    # Cấp quyền Admin cho tài khoản có UUID được chỉ định trong biến môi trường ADMIN_USER_ID
    admin_id = os.getenv("ADMIN_USER_ID", "").strip()
    if admin_id:
        with engine.begin() as con:
            con.execute(update(users).where(users.c.id == admin_id).values(is_admin=True))


if __name__ == "__main__":
    init_db()
    print(f"Đã tạo các bảng SQL trên {engine.dialect.name}.")
