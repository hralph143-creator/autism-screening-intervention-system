import os
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="autism_stage1_test_"))
os.environ["APP_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["APP_ENV"] = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from backend.app.core.database import SessionLocal, initialize_database
from backend.app.main import app
from backend.app.models.child import Child
from backend.app.models.user import AuthSession, User


@pytest.fixture(autouse=True)
def clean_database():
    initialize_database()
    with SessionLocal() as db:
        db.execute(delete(Child))
        db.execute(delete(AuthSession))
        db.execute(delete(User))
        db.commit()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def authenticated_client(client):
    response = client.post("/api/auth/initialize", json={"username": "阶段二管理员", "password": "Secure123", "confirm_password": "Secure123"})
    assert response.status_code == 201
    return client
