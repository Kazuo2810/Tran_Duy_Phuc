"""Kết nối SQL và khai báo bảng dữ liệu."""

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

database_url = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{ROOT / 'iris.db'}",
)

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1,
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

engine_options = {"pool_pre_ping": True}

if database_url.startswith("sqlite"):
    engine_options["connect_args"] = {
        "check_same_thread": False,
    }


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

    database_url = URL.create(
        "mssql+pyodbc",
        query={"odbc_connect": connection_string},
    )

    # Bỏ tùy chọn chỉ dùng cho SQLite.
    engine_options = {"pool_pre_ping": True}

engine = create_engine(database_url, **engine_options)
admin_default = "0" if engine.dialect.name == "mssql" else "false"
metadata = MetaData()


# Giữ bảng phiên cũ để không làm mất dữ liệu hiện có.
# API đăng nhập mới không sử dụng bảng này.
sessions = Table(
    "iris_sessions",
    metadata,
    Column("owner", String(64), primary_key=True),
    Column("name", Unicode(80), nullable=False),
)


# Tài khoản: chỉ lưu mật khẩu đã băm bằng Argon2.
users = Table(
    "iris_users",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "username",
        String(80),
        nullable=False,
        unique=True,
        index=True,
    ),
    Column("name", Unicode(80), nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("is_admin", Boolean, nullable=False, default=False, server_default=text(admin_default)),
)


# SQL chỉ lưu bản băm của token đăng nhập.
auth_sessions = Table(
    "iris_auth_sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column(
        "user_id",
        String(36),
        ForeignKey("iris_users.id"),
        nullable=False,
        index=True,
    ),
    Column("created_at", String(40), nullable=False),
    Column("expires_at", Float, nullable=False),
)


logs = {}

for model in MODEL_NAMES:
    logs[model] = Table(
        f"logs_{model.lower()}",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("owner", String(64), nullable=False, index=True),
        Column("time", String(40), nullable=False, index=True),
        Column("user", Unicode(80), nullable=False),
        Column("model", String(8), nullable=False),
        Column("version", String(32), nullable=False),
        Column("sepal_length", Float, nullable=False),
        Column("sepal_width", Float, nullable=False),
        Column("petal_length", Float, nullable=False),
        Column("petal_width", Float, nullable=False),
        Column("result", String(40), nullable=False),
        Column("elapsed_ms", Float, nullable=False),
    )


def init_db():
    # Migration for databases created before the admin feature.
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
    # Only the exact existing account UUID designated by the service owner is promoted.
    admin_id = os.getenv("ADMIN_USER_ID", "").strip()
    if admin_id:
        with engine.begin() as con:
            con.execute(update(users).where(users.c.id == admin_id).values(is_admin=True))


if __name__ == "__main__":
    init_db()
    print(f"Đã tạo các bảng SQL trên {engine.dialect.name}.")
