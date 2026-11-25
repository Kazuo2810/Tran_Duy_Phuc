from datetime import date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

class RegisterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)

class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)

class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    features: dict[str, StrictFloat | StrictInt] = Field(..., description="Đúng 30 đặc trưng từ /metadata")

class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str | None = None
    patient_code: str | None = Field(default=None, min_length=3, max_length=30)
    full_name: str = Field(min_length=1, max_length=150)
    birth_date: date | None = None
    gender: str = Field(default="", max_length=30)
    phone: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=150)
    address: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)

class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, max_length=150)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)

class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=1, max_length=150)
    department: str = Field(default="", max_length=150)
    position: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=30)

class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(pattern=r"^(admin|staff|patient)$")

class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    staff_user_id: str
    patient_id: str

class RecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: str = Field(min_length=2, max_length=50)
    record_data: dict[str, Any]
