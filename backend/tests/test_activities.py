import json
from datetime import date, timedelta

from sqlalchemy import func, select

from backend.app.core.database import SessionLocal, engine, initialize_database
from backend.app.migrations import run_migrations
from backend.app.models.activity import Activity, ActivityRecord
from backend.app.models.child import Child
from backend.app.models.observation import ObservationRecord
from backend.app.models.video_analysis import VideoAnalysis


def create_child(client, nickname="活动测试档案", birth_month="2020-06") -> dict:
    response = client.post("/api/children", json={"nickname":nickname,"birth_month":birth_month})
    assert response.status_code == 201
    return response.json()


def first_activity(client, category=None) -> dict:
    params={"page_size":100}
    if category: params["category"]=category
    response=client.get("/api/activities",params=params)
    assert response.status_code==200 and response.json()["items"]
    return response.json()["items"][0]


def activity_payload(**updates) -> dict:
    payload={"activity_code":"ACT-CUS-TEST01","name":"家庭节奏游戏","category":"社交互动","age_min_months":24,"age_max_months":120,"objective":"在轻松节奏中共同参与。","materials":["软垫"],"steps":["成人示范简单节奏。","儿童愿意时共同尝试。"],"suggested_duration_minutes":8,"precautions":"尊重拒绝，不强迫参与，明显不适时停止。"}
    payload.update(updates); return payload


def record_payload(child_id:int,activity_id:int,**updates)->dict:
    payload={"child_id":child_id,"activity_id":activity_id,"activity_date":date.today().isoformat(),"completion_status":"COMPLETED","actual_duration_minutes":8,"child_response":"共同进行了两轮，中途主动休息。","notes":"家庭日常记录。"}
    payload.update(updates); return payload


def test_builtin_seed_has_twelve_items_and_is_idempotent_without_overwrite():
    with SessionLocal() as db:
        items=db.scalars(select(Activity).order_by(Activity.activity_code)).all()
        assert len(items)==12 and all(item.is_builtin for item in items)
        counts={category:sum(item.category==category for item in items) for category in {item.category for item in items}}
        assert set(counts.values())=={3}
        items[0].name="管理员保留的修改"; db.commit(); modified_code=items[0].activity_code
    initialize_database(); run_migrations(engine)
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Activity.id)))==12
        assert db.scalar(select(Activity.name).where(Activity.activity_code==modified_code))=="管理员保留的修改"


def test_activity_routes_require_authentication(client):
    assert client.get("/api/activities").status_code==401
    assert client.post("/api/activities",json=activity_payload()).status_code==401
    assert client.get("/api/activity-records").status_code==401
    assert client.get("/api/activity-records/stats").status_code==401


def test_activity_list_search_category_detail_and_age_filter(authenticated_client):
    child=create_child(authenticated_client,birth_month="2020-06")
    listing=authenticated_client.get("/api/activities",params={"page_size":100})
    assert listing.status_code==200 and listing.json()["total"]==12
    assert len(listing.json()["categories"])==4 and "医疗干预方案" in listing.json()["disclaimer"]
    category=authenticated_client.get("/api/activities",params={"category":"语言与沟通","page_size":100}).json()
    assert category["total"]==3 and all(item["category"]=="语言与沟通" for item in category["items"])
    search=authenticated_client.get("/api/activities",params={"q":"绘本"}).json()
    assert search["total"]==1 and search["items"][0]["name"]=="绘本共读"
    detail=authenticated_client.get(f"/api/activities/{search['items'][0]['id']}")
    assert detail.status_code==200 and len(detail.json()["steps"])>=3
    aged=authenticated_client.get("/api/activities",params={"child_id":child["id"],"page_size":100}).json()
    assert aged["age_filter"]["applied"] is True and aged["age_filter"]["age_months"] is not None
    no_birth=create_child(authenticated_client,"无出生年月",None)
    no_age=authenticated_client.get("/api/activities",params={"child_id":no_birth["id"]}).json()
    assert no_age["age_filter"]["applied"] is False and no_age["age_filter"]["age_months"] is None


def test_create_edit_and_deactivate_activity(authenticated_client):
    created=authenticated_client.post("/api/activities",json=activity_payload())
    assert created.status_code==201 and created.json()["is_builtin"] is False
    duplicate=authenticated_client.post("/api/activities",json=activity_payload())
    assert duplicate.status_code==409
    activity_id=created.json()["id"]
    update=activity_payload(name="修改后的互动活动",category="语言与沟通"); update.pop("activity_code")
    edited=authenticated_client.put(f"/api/activities/{activity_id}",json=update)
    assert edited.status_code==200 and edited.json()["name"]=="修改后的互动活动"
    disabled=authenticated_client.patch(f"/api/activities/{activity_id}/status",json={"is_active":False})
    assert disabled.status_code==200 and disabled.json()["is_active"] is False
    assert all(item["id"]!=activity_id for item in authenticated_client.get("/api/activities",params={"page_size":100}).json()["items"])
    assert any(item["id"]==activity_id for item in authenticated_client.get("/api/activities",params={"active_only":False,"page_size":100}).json()["items"])


def test_record_create_persist_duplicate_and_detail(authenticated_client):
    child=create_child(authenticated_client); activity=first_activity(authenticated_client)
    created=authenticated_client.post("/api/activity-records",json=record_payload(child["id"],activity["id"]))
    assert created.status_code==201
    record=created.json(); assert record["activity_name"]==activity["name"] and record["completion_label"]=="已完成"
    assert authenticated_client.post("/api/activity-records",json=record_payload(child["id"],activity["id"])).status_code==409
    with SessionLocal() as db:
        stored=db.get(ActivityRecord,record["id"]); assert stored is not None and stored.activity_name_snapshot==activity["name"]
    initialize_database()
    assert authenticated_client.get(f"/api/activity-records/{record['id']}").status_code==200


def test_record_validation_rejects_bad_child_activity_status_duration_and_date(authenticated_client):
    child=create_child(authenticated_client); activity=first_activity(authenticated_client)
    invalid=[
        record_payload(999999,activity["id"]),
        record_payload(child["id"],999999),
        record_payload(child["id"],activity["id"],completion_status="EXCELLENT"),
        record_payload(child["id"],activity["id"],actual_duration_minutes=-1),
        record_payload(child["id"],activity["id"],actual_duration_minutes=481),
        record_payload(child["id"],activity["id"],activity_date=(date.today()+timedelta(days=1)).isoformat()),
    ]
    expected=[404,404,422,422,422,422]
    for payload,code in zip(invalid,expected): assert authenticated_client.post("/api/activity-records",json=payload).status_code==code
    authenticated_client.patch(f"/api/activities/{activity['id']}/status",json={"is_active":False})
    assert authenticated_client.post("/api/activity-records",json=record_payload(child["id"],activity["id"])).status_code==422


def test_record_edit_delete_and_inactive_history_snapshot(authenticated_client):
    child=create_child(authenticated_client); activity=first_activity(authenticated_client)
    record=authenticated_client.post("/api/activity-records",json=record_payload(child["id"],activity["id"])).json()
    edit_body={key:value for key,value in activity_payload(name="资源名称已修改").items() if key!="activity_code"}
    authenticated_client.put(f"/api/activities/{activity['id']}",json=edit_body)
    authenticated_client.patch(f"/api/activities/{activity['id']}/status",json={"is_active":False})
    detail=authenticated_client.get(f"/api/activity-records/{record['id']}").json()
    assert detail["activity_name"]==activity["name"] and detail["activity_is_active"] is False
    updated=authenticated_client.put(f"/api/activity-records/{record['id']}",json=record_payload(child["id"],activity["id"],completion_status="PARTIAL",actual_duration_minutes=5))
    assert updated.status_code==200 and updated.json()["completion_label"]=="部分完成"
    assert updated.json()["activity_name"]==activity["name"]
    assert authenticated_client.delete(f"/api/activity-records/{record['id']}").status_code==200
    assert authenticated_client.get(f"/api/activity-records/{record['id']}").status_code==404


def test_record_filters_child_history_and_statistics(authenticated_client):
    first=create_child(authenticated_client,"甲"); second=create_child(authenticated_client,"乙")
    social=first_activity(authenticated_client,"社交互动"); communication=first_activity(authenticated_client,"语言与沟通")
    yesterday=(date.today()-timedelta(days=1)).isoformat()
    authenticated_client.post("/api/activity-records",json=record_payload(first["id"],social["id"],activity_date=yesterday,completion_status="COMPLETED"))
    authenticated_client.post("/api/activity-records",json=record_payload(first["id"],communication["id"],completion_status="PARTIAL"))
    authenticated_client.post("/api/activity-records",json=record_payload(second["id"],social["id"],completion_status="NOT_COMPLETED",actual_duration_minutes=None))
    history=authenticated_client.get(f"/api/children/{first['id']}/activity-records",params={"category":"社交互动"}).json()
    assert history["total"]==1 and history["items"][0]["child_id"]==first["id"]
    dated=authenticated_client.get("/api/activity-records",params={"date_from":date.today().isoformat(),"date_to":date.today().isoformat()}).json()
    assert dated["total"]==2
    stats=authenticated_client.get("/api/activity-records/stats").json()
    assert stats["total_records"]==3 and stats["completed_records"]==1 and stats["partial_records"]==1 and stats["not_completed_records"]==1
    assert stats["category_counts"]["社交互动"]==2 and stats["latest_activity_date"]==date.today().isoformat()


def test_child_delete_cascades_records_but_not_activity_resources(authenticated_client):
    child=create_child(authenticated_client); activity=first_activity(authenticated_client)
    record=authenticated_client.post("/api/activity-records",json=record_payload(child["id"],activity["id"])).json()
    assert authenticated_client.delete(f"/api/children/{child['id']}").status_code==200
    with SessionLocal() as db:
        assert db.get(ActivityRecord,record["id"]) is None
        assert db.get(Activity,activity["id"]) is not None


def test_migration_0005_preserves_previous_stage_rows(authenticated_client):
    child=create_child(authenticated_client)
    with SessionLocal() as db:
        video=VideoAnalysis(child_id=child["id"],original_filename="keep.mp4",stored_filename="keep-stage5.mp4",file_path="unused",file_sha256="f"*64,file_size=1,duration_seconds=1,width=100,height=100,source_fps=10,status="FAILED")
        db.add(video); db.flush()
        observation=ObservationRecord(child_id=child["id"],video_analysis_id=video.id,observation_date=date.today(),observation_scene="家庭日常",observer_role="家长",observation_data=json.dumps({"initiates_interaction":"OFTEN"},ensure_ascii=False))
        db.add(observation); db.commit(); video_id=video.id; observation_id=observation.id
    run_migrations(engine); run_migrations(engine); initialize_database()
    with SessionLocal() as db:
        assert db.get(Child,child["id"]) is not None
        assert db.get(VideoAnalysis,video_id) is not None
        assert db.get(ObservationRecord,observation_id) is not None
        assert db.scalar(select(func.count(Activity.id)))==12
