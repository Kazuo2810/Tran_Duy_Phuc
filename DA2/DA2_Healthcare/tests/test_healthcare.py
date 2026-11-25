import uuid
import time
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from app.main import app
from app import database
from app.routers import auth as auth_router

SECRET = "test-secret-for-healthcare-only-32-bytes-min"
ISSUER = "http://test-idp"
CLIENT = "healthcare-web"

@pytest.fixture(autouse=True)
def clean_db(monkeypatch):
    database.init_db()
    with database.engine.begin() as con:
        for table in reversed(database.metadata.sorted_tables):
            con.execute(delete(table))
    yield

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def fake_idp(monkeypatch):
    users = {}
    async def fake(path, payload):
        username = payload["username"].lower()
        if path.endswith("register"):
            if username in users:
                from fastapi import HTTPException
                raise HTTPException(409, "Tên đăng nhập đã tồn tại.")
            users[username] = {"id": str(uuid.uuid4()), "username": username,
                              "name": payload["name"], "is_admin": username == "root_admin"}
        else:
            if username not in users:
                users[username] = {"id": str(uuid.uuid4()), "username": username,
                                  "name": payload.get("name", username), "is_admin": username == "root_admin"}
        user = users[username]
        claims = {"iss": ISSUER, "sub": user["id"], "username": username,
                  "name": user["name"], "is_admin": user["is_admin"],
                  "client_id": CLIENT, "aud": CLIENT,
                  "scope": ["healthcare:access"], "iat": int(time.time()), "exp": int(time.time()) + 3600}
        token = jwt.encode(claims, SECRET, algorithm="HS256")
        return {"access_token": token, "expires_in": 3600, "user": user}
    monkeypatch.setattr(auth_router, "idp_auth", fake)
    return users

def register(client, username, name=None):
    r = client.post("/api/register", json={"username": username, "name": name or username.title(), "password": "demo-password-123"})
    assert r.status_code == 201, r.text
    return r.json()

def login(client, username):
    r = client.post("/api/login", json={"username": username, "password": "demo-password-123"})
    assert r.status_code == 200, r.text
    return r.json()

def headers(session):
    return {"X-CSRF-Token": session["csrf"]}

def test_public_model_api(client):
    assert client.get("/health").status_code == 200
    assert len(client.get("/metadata").json()["feature_names"]) == 30
    sample = client.get("/api/sample").json()
    result = client.post("/predict", json=sample)
    assert result.status_code == 200
    assert result.json()["predicted_label"] in ("malignant", "benign")

def test_patient_staff_admin_assignment_and_isolation(client, fake_idp):
    # Tạo Admin đầu tiên thông qua tài khoản Admin IdP.
    register(client, "root_admin", "Quản trị viên")
    admin_session = login(client, "root_admin")
    assert admin_session["user"]["role"] == "patient"
    boot = client.post("/api/admin/bootstrap", json={}, headers=headers(admin_session))
    assert boot.status_code == 200, boot.text
    admin_session = client.get("/api/me").json()
    assert admin_session["user"]["role"] == "admin"

    # Hai bệnh nhân tự đăng ký, mỗi tài khoản có hồ sơ riêng.
    patient_a = register(client, "patient_a", "Bệnh nhân A")
    patient_a_login = login(client, "patient_a")
    patient_b = register(client, "patient_b", "Bệnh nhân B")
    patient_b_login = login(client, "patient_b")

    # Tài khoản nhân viên đăng ký trước, sau đó Admin cấp vai trò staff.
    register(client, "staff_a", "Nhân viên A")
    admin_session = login(client, "root_admin")
    staff_row = next(x for x in client.get("/api/admin/users").json()["items"] if x["username"] == "staff_a")
    changed = client.patch(f"/api/admin/users/{staff_row['id']}/role", json={"role": "staff"}, headers=headers(admin_session))
    assert changed.status_code == 200, changed.text
    staff_login = login(client, "staff_a")
    admin_session = login(client, "root_admin")

    # Admin chỉ định nhân viên A quản lý bệnh nhân A.
    patients = client.get("/api/patients").json()["items"]
    p_a = next(p for p in patients if p["full_name"] == "Bệnh nhân A")
    p_b = next(p for p in patients if p["full_name"] == "Bệnh nhân B")
    assigned = client.post("/api/admin/assignments", json={
        "staff_user_id": staff_row["id"], "patient_id": p_a["id"]
    }, headers=headers(admin_session))
    assert assigned.status_code == 201, assigned.text

    # Staff chỉ nhìn thấy bệnh nhân được phân công.
    staff_login = login(client, "staff_a")
    staff_patients = client.get("/api/patients").json()["items"]
    assert [p["id"] for p in staff_patients] == [p_a["id"]]
    assert client.get(f"/api/patients/{p_b['id']}").status_code == 404

    # Nhân viên dự đoán cho bệnh nhân được phân công và lưu lịch sử.
    sample = client.get("/api/sample").json()
    pred = client.post(f"/api/patients/{p_a['id']}/predict", json=sample, headers=headers(staff_login))
    assert pred.status_code == 200, pred.text
    assert client.get("/api/history").json()["count"] == 1

    # Bệnh nhân B không thể xem hồ sơ hoặc lịch sử của A.
    patient_b_login = login(client, "patient_b")
    assert client.get(f"/api/patients/{p_a['id']}").status_code == 404
    assert client.get("/api/history").json()["count"] == 0


def test_csrf_and_patient_edit_limits(client, fake_idp):
    register(client, "patient_x", "Bệnh nhân X")
    session = login(client, "patient_x")
    patient = client.get("/api/patients").json()["items"][0]
    assert client.put(f"/api/patients/{patient['id']}", json={"phone": "0900000000"}).status_code == 403
    assert client.put(f"/api/patients/{patient['id']}", json={"phone": "0900000000"}, headers=headers(session)).status_code == 200
    assert client.put(f"/api/patients/{patient['id']}", json={"full_name": "Đổi tên"}, headers=headers(session)).status_code == 403
    assert client.get("/api/me").status_code == 200
    assert client.post("/api/logout", json={}, headers=headers(session)).status_code == 200
    assert client.get("/api/me").status_code == 401
