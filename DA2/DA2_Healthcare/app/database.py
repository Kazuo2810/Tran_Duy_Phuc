"""PostgreSQL schema riêng cho Healthcare; SQLite chỉ dùng khi phát triển local."""
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import (
    create_engine, MetaData, Table, Column, String, Boolean, Date, DateTime,
    Float, Text, ForeignKey, UniqueConstraint, CheckConstraint, Index, JSON, text
)
from sqlalchemy.dialects.postgresql import JSONB

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{Path(__file__).resolve().parents[1] / 'healthcare.db'}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_options)
SCHEMA = os.getenv("DB_SCHEMA", "healthcare") if engine.dialect.name == "postgresql" else None
if SCHEMA and not re.fullmatch(r"[a-z_][a-z0-9_]*", SCHEMA):
    raise RuntimeError("DB_SCHEMA phải là tên schema PostgreSQL hợp lệ.")
metadata = MetaData(schema=SCHEMA)
json_type = JSON().with_variant(JSONB, "postgresql")
prefix = f"{SCHEMA}." if SCHEMA else ""

app_users = Table(
    "app_users", metadata,
    Column("id", String(64), primary_key=True),  # JWT sub do IdP cấp
    Column("username", String(100), nullable=False, unique=True),
    Column("display_name", String(150), nullable=False, default=""),
    Column("role", String(20), nullable=False, default="patient"),
    Column("status", String(20), nullable=False, default="active"),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    CheckConstraint("role IN ('admin','staff','patient')", name="ck_healthcare_user_role"),
    CheckConstraint("status IN ('active','inactive')", name="ck_healthcare_user_status"),
)

staff_profiles = Table(
    "staff_profiles", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(64), ForeignKey(f"{prefix}app_users.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("full_name", String(150), nullable=False),
    Column("department", String(150), nullable=False, default=""),
    Column("position", String(100), nullable=False, default=""),
    Column("phone", String(30), nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

patient_profiles = Table(
    "patient_profiles", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(64), ForeignKey(f"{prefix}app_users.id", ondelete="SET NULL"), nullable=True, unique=True),
    Column("patient_code", String(30), nullable=False, unique=True),
    Column("full_name", String(150), nullable=False),
    Column("birth_date", Date, nullable=True),
    Column("gender", String(30), nullable=False, default=""),
    Column("phone", String(30), nullable=False, default=""),
    Column("email", String(150), nullable=False, default=""),
    Column("address", Text, nullable=False, default=""),
    Column("notes", Text, nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

staff_patient_assignments = Table(
    "staff_patient_assignments", metadata,
    Column("id", String(36), primary_key=True),
    Column("staff_id", String(36), ForeignKey(f"{prefix}staff_profiles.id", ondelete="CASCADE"), nullable=False),
    Column("patient_id", String(36), ForeignKey(f"{prefix}patient_profiles.id", ondelete="CASCADE"), nullable=False),
    Column("assigned_by", String(64), ForeignKey(f"{prefix}app_users.id", ondelete="SET NULL"), nullable=True),
    Column("assigned_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("status", String(20), nullable=False, default="active"),
    UniqueConstraint("staff_id", "patient_id", name="uq_healthcare_staff_patient"),
    CheckConstraint("status IN ('active','inactive')", name="ck_healthcare_assignment_status"),
)

patient_records = Table(
    "patient_records", metadata,
    Column("id", String(36), primary_key=True),
    Column("patient_id", String(36), ForeignKey(f"{prefix}patient_profiles.id", ondelete="CASCADE"), nullable=False),
    Column("created_by", String(64), ForeignKey(f"{prefix}app_users.id", ondelete="SET NULL"), nullable=True),
    Column("record_type", String(50), nullable=False),
    Column("record_data", json_type, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

prediction_history = Table(
    "prediction_history", metadata,
    Column("id", String(36), primary_key=True),
    Column("patient_id", String(36), ForeignKey(f"{prefix}patient_profiles.id", ondelete="CASCADE"), nullable=False),
    Column("created_by", String(64), ForeignKey(f"{prefix}app_users.id", ondelete="SET NULL"), nullable=True),
    Column("model_name", String(100), nullable=False),
    Column("model_version", String(50), nullable=False),
    Column("features", json_type, nullable=False),
    Column("predicted_class", String(20), nullable=False),
    Column("predicted_label", String(30), nullable=False),
    Column("probability_malignant", Float, nullable=False),
    Column("probability_benign", Float, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

audit_logs = Table(
    "audit_logs", metadata,
    Column("id", String(36), primary_key=True),
    Column("actor_id", String(64), ForeignKey(f"{prefix}app_users.id", ondelete="SET NULL"), nullable=True),
    Column("action", String(100), nullable=False),
    Column("resource_type", String(100), nullable=False, default=""),
    Column("resource_id", String(64), nullable=False, default=""),
    Column("metadata", json_type, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

Index("ix_healthcare_assignment_staff_status", staff_patient_assignments.c.staff_id, staff_patient_assignments.c.status)
Index("ix_healthcare_assignment_patient_status", staff_patient_assignments.c.patient_id, staff_patient_assignments.c.status)
Index("ix_healthcare_prediction_patient_time", prediction_history.c.patient_id, prediction_history.c.created_at)
Index("ix_healthcare_audit_actor_time", audit_logs.c.actor_id, audit_logs.c.created_at)


def init_db():
    if SCHEMA:
        with engine.begin() as con:
            con.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    metadata.create_all(engine)


def table(name: str):
    return metadata.tables[f"{SCHEMA + '.' if SCHEMA else ''}{name}"]
