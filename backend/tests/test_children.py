from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from backend.app.core.database import Base
from backend.app.core.security import hash_password
from backend.app.migrations import run_migrations
from backend.app.models.user import AuthSession, User


def payload(nickname="小树", birth_month="2020-06"):
    return {"nickname": nickname, "birth_month": birth_month, "gender": "未说明", "development_notes": "喜欢拼图", "guardian_notes": "使用化名记录"}


def test_create_requires_fields_and_generates_unique_codes(authenticated_client):
    assert authenticated_client.post("/api/children", json={"birth_month": "2020-01"}).status_code == 422
    first = authenticated_client.post("/api/children", json=payload("档案一"))
    second = authenticated_client.post("/api/children", json=payload("档案二"))
    assert first.status_code == second.status_code == 201
    assert first.json()["child_code"].startswith("CH-")
    assert first.json()["child_code"] != second.json()["child_code"]
    assert first.json()["age_text"] != "未填写"


def test_validation_rejects_future_birth_month_and_long_search(authenticated_client):
    assert authenticated_client.post("/api/children", json=payload("未来档案", "2999-01")).status_code == 422
    assert authenticated_client.get("/api/children", params={"q": "x" * 51}).status_code == 422


def test_list_search_sort_and_pagination(authenticated_client):
    for index in range(12):
        assert authenticated_client.post("/api/children", json=payload(f"分页档案{index:02d}", None)).status_code == 201
    page_one = authenticated_client.get("/api/children", params={"page": 1, "page_size": 5}).json()
    page_three = authenticated_client.get("/api/children", params={"page": 3, "page_size": 5}).json()
    assert page_one["total"] == 12 and len(page_one["items"]) == 5
    assert len(page_three["items"]) == 2
    search = authenticated_client.get("/api/children", params={"q": "分页档案03"}).json()
    assert search["total"] == 1 and search["items"][0]["nickname"] == "分页档案03"
    code = page_one["items"][0]["child_code"]
    assert authenticated_client.get("/api/children", params={"q": code}).json()["total"] == 1
    ascending = authenticated_client.get("/api/children", params={"sort_order": "asc"}).json()["items"]
    assert ascending[0]["id"] < page_one["items"][0]["id"]


def test_detail_update_keeps_code_and_delete(authenticated_client):
    created = authenticated_client.post("/api/children", json=payload()).json()
    detail = authenticated_client.get(f"/api/children/{created['id']}")
    assert detail.status_code == 200 and detail.json()["guardian_notes"] == "使用化名记录"
    updated_payload = payload("新昵称", "2021-08"); updated_payload["guardian_notes"] = "已更新"
    updated = authenticated_client.put(f"/api/children/{created['id']}", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["nickname"] == "新昵称"
    assert updated.json()["child_code"] == created["child_code"]
    assert authenticated_client.delete(f"/api/children/{created['id']}").status_code == 200
    assert authenticated_client.get(f"/api/children/{created['id']}").status_code == 404
    assert authenticated_client.delete("/api/children/999999").status_code == 404


def test_all_children_endpoints_require_login(client):
    assert client.get("/api/children").status_code == 401
    assert client.post("/api/children", json=payload()).status_code == 401
    assert client.get("/api/children/1").status_code == 401
    assert client.put("/api/children/1", json=payload()).status_code == 401
    assert client.delete("/api/children/1").status_code == 401
    assert client.get("/api/dashboard/stats").status_code == 401


def test_dashboard_stats_and_persistence(authenticated_client):
    first = authenticated_client.post("/api/children", json=payload("统计一")).json()
    authenticated_client.post("/api/children", json=payload("统计二"))
    stats = authenticated_client.get("/api/dashboard/stats").json()
    assert stats["total_children"] == 2
    assert stats["added_this_month"] == 2
    assert len(stats["recent_children"]) == 2
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as restarted:
        assert restarted.post("/api/auth/login", json={"username": "阶段二管理员", "password": "Secure123"}).status_code == 200
        assert restarted.get(f"/api/children/{first['id']}").json()["nickname"] == "统计一"


def test_migration_preserves_existing_admin(tmp_path: Path):
    target = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    Base.metadata.create_all(bind=target, tables=[User.__table__, AuthSession.__table__])
    with Session(target) as db:
        db.add(User(singleton_slot=1, username="原管理员", password_hash=hash_password("Secure123")))
        db.commit()
    run_migrations(target)
    run_migrations(target)
    assert "children" in inspect(target).get_table_names()
    with Session(target) as db:
        assert db.scalar(select(User.username)) == "原管理员"

