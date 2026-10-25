import json
from datetime import date, timedelta

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal, engine
from backend.app.migrations import run_migrations
from backend.app.models.child import Child
from backend.app.models.observation import ObservationRecord
from backend.app.models.video_analysis import VideoAnalysis


def create_child(client, nickname="观察测试档案") -> dict:
    response = client.post("/api/children", json={"nickname": nickname})
    assert response.status_code == 201
    return response.json()


def observation_payload(child_id: int, **updates) -> dict:
    payload = {
        "child_id": child_id,
        "video_analysis_id": None,
        "observation_date": date.today().isoformat(),
        "observation_scene": "游戏活动",
        "observer_role": "家长",
        "observation_data": {
            "initiates_interaction": "OFTEN",
            "responds_to_name": "UNABLE_TO_JUDGE",
            "joins_shared_activity": "NOT_OBSERVED",
            "expresses_needs": "NOT_SEEN_THIS_TIME",
        },
        "summary_notes": "在安静的家庭环境中记录。",
    }
    payload.update(updates)
    return payload


def add_video(child_id: int, status="FAILED") -> int:
    with SessionLocal() as db:
        video = VideoAnalysis(
            child_id=child_id,
            original_filename=f"{child_id}.mp4",
            stored_filename=f"observation-{child_id}-{status}.mp4",
            file_path=f"unused-{child_id}.mp4",
            file_sha256=(str(child_id) * 64)[:64],
            file_size=1,
            duration_seconds=1,
            width=160,
            height=120,
            source_fps=10,
            status=status,
            error_message="测试失败" if status == "FAILED" else None,
            result_json=json.dumps({"summary": {"sampled_frames": 18}}, ensure_ascii=False) if status == "COMPLETED" else None,
        )
        db.add(video); db.commit(); db.refresh(video)
        return video.id


def test_observation_routes_require_authentication(client):
    assert client.get("/api/observations").status_code == 401
    assert client.get("/api/observations/form-definition").status_code == 401
    assert client.post("/api/observations", json=observation_payload(1)).status_code == 401


def test_form_definition_is_neutral_and_distinguishes_missing_states(authenticated_client):
    response = authenticated_client.get("/api/observations/form-definition")
    assert response.status_code == 200
    payload = response.json()
    labels = {item["label"] for item in payload["options"]}
    assert {"本次未观察到", "无法判断", "未观察"} <= labels
    assert len(payload["dimensions"]) == 6
    text = json.dumps(payload, ensure_ascii=False)
    assert "患病概率" not in text and "风险等级" not in text


def test_create_query_persist_and_dynamic_summary(authenticated_client):
    child = create_child(authenticated_client)
    response = authenticated_client.post("/api/observations", json=observation_payload(child["id"]))
    assert response.status_code == 201
    record = response.json()
    assert record["child_code"] == child["child_code"]
    assert "社交互动" in record["auxiliary_summary"]
    assert "1项无法判断" in record["auxiliary_summary"]
    assert "1项明确标记为未观察" in record["auxiliary_summary"]
    assert record["data_completeness"]["recorded_items"] == 4
    assert record["disclaimer"].startswith("本记录用于日常行为观察")
    with SessionLocal() as db:
        stored = db.get(ObservationRecord, record["id"])
        assert stored is not None and json.loads(stored.observation_data)["initiates_interaction"] == "OFTEN"
    detail = authenticated_client.get(f"/api/observations/{record['id']}")
    assert detail.status_code == 200 and detail.json()["summary_notes"] == "在安静的家庭环境中记录。"


def test_edit_delete_and_missing_record(authenticated_client):
    child = create_child(authenticated_client)
    created = authenticated_client.post("/api/observations", json=observation_payload(child["id"])).json()
    updated_payload = observation_payload(
        child["id"], observation_scene="家庭日常", observer_role="其他监护人",
        observation_data={"responds_to_name": "SOMETIMES"}, summary_notes="  更新后的记录  "
    )
    updated = authenticated_client.put(f"/api/observations/{created['id']}", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["observation_scene"] == "家庭日常"
    assert updated.json()["summary_notes"] == "更新后的记录"
    deleted = authenticated_client.delete(f"/api/observations/{created['id']}")
    assert deleted.status_code == 200
    assert authenticated_client.get(f"/api/observations/{created['id']}").status_code == 404
    assert authenticated_client.put("/api/observations/999999", json=updated_payload).status_code == 404
    assert authenticated_client.delete("/api/observations/999999").status_code == 404


def test_child_history_date_filter_and_pagination(authenticated_client):
    first = create_child(authenticated_client, "甲")
    second = create_child(authenticated_client, "乙")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    authenticated_client.post("/api/observations", json=observation_payload(first["id"], observation_date=yesterday))
    authenticated_client.post("/api/observations", json=observation_payload(first["id"]))
    authenticated_client.post("/api/observations", json=observation_payload(second["id"]))
    history = authenticated_client.get(f"/api/children/{first['id']}/observations", params={"date_from": date.today().isoformat(), "page_size": 1})
    assert history.status_code == 200
    assert history.json()["total"] == 1 and history.json()["items"][0]["child_id"] == first["id"]
    listing = authenticated_client.get("/api/observations", params={"child_id": first["id"], "page_size": 1})
    assert listing.json()["total"] == 2 and len(listing.json()["items"]) == 1


def test_invalid_dates_options_scene_role_and_notes(authenticated_client):
    child = create_child(authenticated_client)
    invalid_payloads = [
        observation_payload(child["id"], observation_date=(date.today() + timedelta(days=1)).isoformat()),
        observation_payload(child["id"], observation_date="1999-12-31"),
        observation_payload(child["id"], observation_scene="医院诊断"),
        observation_payload(child["id"], observer_role="陌生身份"),
        observation_payload(child["id"], observation_data={"responds_to_name": "ALWAYS"}),
        observation_payload(child["id"], observation_data={"unknown_item": "OFTEN"}),
        observation_payload(child["id"], observation_data={}),
        observation_payload(child["id"], summary_notes="字" * 4001),
    ]
    for payload in invalid_payloads:
        assert authenticated_client.post("/api/observations", json=payload).status_code == 422
    reversed_range = authenticated_client.get("/api/observations", params={"date_from": date.today(), "date_to": date.today() - timedelta(days=1)})
    assert reversed_range.status_code == 422


def test_nonexistent_child_and_cross_child_video_are_rejected(authenticated_client):
    first = create_child(authenticated_client, "甲")
    second = create_child(authenticated_client, "乙")
    video_id = add_video(first["id"])
    assert authenticated_client.post("/api/observations", json=observation_payload(999999)).status_code == 404
    cross = authenticated_client.post("/api/observations", json=observation_payload(second["id"], video_analysis_id=video_id))
    assert cross.status_code == 422
    missing_video = authenticated_client.post("/api/observations", json=observation_payload(first["id"], video_analysis_id=999999))
    assert missing_video.status_code == 404


def test_failed_video_can_be_linked_without_fake_results(authenticated_client):
    child = create_child(authenticated_client)
    video_id = add_video(child["id"], "FAILED")
    response = authenticated_client.post("/api/observations", json=observation_payload(child["id"], video_analysis_id=video_id))
    assert response.status_code == 201
    linked = response.json()["linked_video"]
    assert linked["status"] == "FAILED" and linked["sampled_frames"] is None
    completed_id = add_video(child["id"], "COMPLETED")
    completed = authenticated_client.put(
        f"/api/observations/{response.json()['id']}",
        json=observation_payload(child["id"], video_analysis_id=completed_id),
    )
    assert completed.status_code == 200
    assert completed.json()["linked_video"]["sampled_frames"] == 18


def test_deleting_video_keeps_observation_and_clears_optional_link(authenticated_client):
    child = create_child(authenticated_client)
    video_id = add_video(child["id"])
    record = authenticated_client.post("/api/observations", json=observation_payload(child["id"], video_analysis_id=video_id)).json()
    with SessionLocal() as db:
        db.delete(db.get(VideoAnalysis, video_id)); db.commit()
    detail = authenticated_client.get(f"/api/observations/{record['id']}")
    assert detail.status_code == 200
    assert detail.json()["video_analysis_id"] is None and detail.json()["linked_video"] is None


def test_migration_is_idempotent_and_preserves_existing_rows(authenticated_client):
    child = create_child(authenticated_client)
    record = authenticated_client.post("/api/observations", json=observation_payload(child["id"])).json()
    run_migrations(engine)
    run_migrations(engine)
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Child.id))) == 1
        assert db.scalar(select(func.count(ObservationRecord.id))) == 1
        assert db.get(ObservationRecord, record["id"]) is not None
