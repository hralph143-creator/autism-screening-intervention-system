from sqlalchemy import inspect, select
from backend.app.core.database import SessionLocal, engine
from backend.app.core.security import verify_password
from backend.app.models.user import User


def initialize(client):
    return client.post("/api/auth/initialize", json={"username": "测试管理员", "password": "Secure123", "confirm_password": "Secure123"})


def test_health_and_database_initialization(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
    assert {"users", "auth_sessions"}.issubset(set(inspect(engine).get_table_names()))


def test_health_reports_database_failure(client, monkeypatch):
    from backend.app.api import health
    monkeypatch.setattr(health, "check_database", lambda: (_ for _ in ()).throw(RuntimeError("数据库测试故障")))
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "数据库连接异常"


def test_admin_initialize_hash_login_protection_and_logout(client):
    created = initialize(client)
    assert created.status_code == 201
    with SessionLocal() as db:
        user = db.scalar(select(User))
        assert user.password_hash != "Secure123"
        assert verify_password("Secure123", user.password_hash)
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/system/info").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/system/info").status_code == 401
    assert client.post("/api/auth/login", json={"username": "测试管理员", "password": "Wrong123"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "测试管理员", "password": "Secure123"}).status_code == 200


def test_repeated_initialization_is_rejected(client):
    assert initialize(client).status_code == 201
    assert initialize(client).status_code == 409


def test_password_validation_schema():
    from pydantic import ValidationError
    from backend.app.schemas.auth import InitializeRequest
    try:
        InitializeRequest(username="admin", password="password", confirm_password="different")
        raise AssertionError("应拒绝弱密码或不一致密码")
    except ValidationError:
        pass


def test_admin_persists_across_client_restart():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as initial:
        assert initialize(initial).status_code == 201
    with TestClient(app) as restarted:
        assert restarted.get("/api/auth/status").json()["initialized"] is True
        assert restarted.post("/api/auth/login", json={"username": "测试管理员", "password": "Secure123"}).status_code == 200
