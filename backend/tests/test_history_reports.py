import json
from datetime import date, datetime, timedelta

from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.models.activity import Activity, ActivityRecord
from backend.app.models.observation import ObservationRecord
from backend.app.models.video_analysis import VideoAnalysis


def create_child(client, nickname="综合历史测试", birth_month="2020-06") -> dict:
    response = client.post("/api/children", json={"nickname": nickname, "birth_month": birth_month, "gender": "未说明"})
    assert response.status_code == 201
    return response.json()


def seed_records(child_id: int, business_date: date | None = None) -> dict:
    selected_date = business_date or date.today()
    with SessionLocal() as db:
        activity = db.scalar(select(Activity).order_by(Activity.id))
        video = VideoAnalysis(
            child_id=child_id, original_filename="真实测试.mp4", stored_filename=f"history-{child_id}-{selected_date}.mp4",
            file_path="private-path", file_sha256=(f"{child_id}{selected_date}" * 64)[:64], file_size=10,
            duration_seconds=6.5, width=640, height=480, source_fps=25, status="COMPLETED",
            result_json=json.dumps({"summary":{"sampled_frames":13,"pose_coverage":0.8,"face_coverage":0.4,"quality_level":"可用"},"motion_statistics":{"upper_limb_change":{"mean":0.2}}}),
            created_at=datetime.combine(selected_date, datetime.min.time()) + timedelta(hours=10),
        )
        db.add(video); db.flush()
        observation = ObservationRecord(
            child_id=child_id, video_analysis_id=video.id, observation_date=selected_date,
            observation_scene="游戏活动", observer_role="家长",
            observation_data=json.dumps({"initiates_interaction":"OFTEN","responds_to_name":"UNABLE_TO_JUDGE"}),
            summary_notes="<script>不会作为 HTML 执行</script>",
        )
        record = ActivityRecord(
            child_id=child_id, activity_id=activity.id, activity_date=selected_date, completion_status="PARTIAL",
            actual_duration_minutes=None, child_response="愿意短暂参与", notes="记录备注",
            activity_code_snapshot=activity.activity_code, activity_name_snapshot="历史活动快照",
            category_snapshot=activity.category, objective_snapshot=activity.objective,
            suggested_duration_snapshot=activity.suggested_duration_minutes,
        )
        db.add_all([observation, record]); db.commit()
        return {"video": video.id, "observation": observation.id, "activity": record.id}


def test_history_and_report_require_authentication(client):
    for path in ("overview", "timeline", "report"):
        assert client.get(f"/api/children/1/{path}").status_code == 401


def test_empty_child_overview_timeline_and_report(authenticated_client):
    child = create_child(authenticated_client)
    overview = authenticated_client.get(f"/api/children/{child['id']}/overview").json()
    assert overview["counts"] == {"video":0,"observation":0,"activity":0}
    assert overview["latest_record_date"] is None
    timeline = authenticated_client.get(f"/api/children/{child['id']}/timeline").json()
    assert timeline["items"] == [] and timeline["total"] == 0
    report = authenticated_client.get(f"/api/children/{child['id']}/report").json()
    assert report["counts"] == {"video":0,"observation":0,"activity":0}
    assert "暂无相关记录" in "".join(report["record_explanation"])


def test_missing_child_and_invalid_filters(authenticated_client):
    for path in ("overview", "timeline", "report"):
        assert authenticated_client.get(f"/api/children/999999/{path}").status_code == 404
    child = create_child(authenticated_client)
    params = {"start_date":date.today().isoformat(),"end_date":(date.today()-timedelta(days=1)).isoformat()}
    assert authenticated_client.get(f"/api/children/{child['id']}/timeline", params=params).status_code == 422
    assert authenticated_client.get(f"/api/children/{child['id']}/report", params={"record_types":"MEDICAL"}).status_code == 422


def test_overview_uses_real_child_counts_and_statistics(authenticated_client):
    child = create_child(authenticated_client); seed_records(child["id"])
    payload = authenticated_client.get(f"/api/children/{child['id']}/overview").json()
    assert payload["child"]["child_code"] == child["child_code"]
    assert payload["counts"] == {"video":1,"observation":1,"activity":1}
    assert payload["monthly_counts"][0]["VIDEO"] == 1
    assert payload["video_status_counts"] == {"COMPLETED":1}
    assert payload["activity_category_counts"]


def test_timeline_filters_dates_types_and_stable_pagination(authenticated_client):
    child = create_child(authenticated_client); today=date.today(); old=today-timedelta(days=5)
    seed_records(child["id"], old); seed_records(child["id"], today)
    first = authenticated_client.get(f"/api/children/{child['id']}/timeline", params={"page_size":2,"page":1}).json()
    second = authenticated_client.get(f"/api/children/{child['id']}/timeline", params={"page_size":2,"page":2}).json()
    assert first["total"] == 6 and len(first["items"]) == len(second["items"]) == 2
    assert {f"{x['record_type']}-{x['record_id']}" for x in first["items"]}.isdisjoint({f"{x['record_type']}-{x['record_id']}" for x in second["items"]})
    video = authenticated_client.get(f"/api/children/{child['id']}/timeline", params={"record_type":"VIDEO"}).json()
    assert video["total"] == 2 and all(item["date_meaning"] == "任务创建日期" for item in video["items"])
    filtered = authenticated_client.get(f"/api/children/{child['id']}/timeline", params={"start_date":today.isoformat(),"end_date":today.isoformat()}).json()
    assert filtered["total"] == 3 and all(item["business_date"] == today.isoformat() for item in filtered["items"])
    ascending = authenticated_client.get(f"/api/children/{child['id']}/timeline", params={"sort_order":"asc","page_size":100}).json()
    assert ascending["items"][0]["business_date"] == old.isoformat()


def test_timeline_isolates_children_and_updates_after_delete(authenticated_client):
    first=create_child(authenticated_client,"儿童一"); second=create_child(authenticated_client,"儿童二")
    ids=seed_records(first["id"]); seed_records(second["id"])
    payload=authenticated_client.get(f"/api/children/{first['id']}/timeline",params={"page_size":100}).json()
    assert payload["total"]==3
    assert authenticated_client.delete(f"/api/observations/{ids['observation']}").status_code==200
    updated=authenticated_client.get(f"/api/children/{first['id']}/timeline",params={"page_size":100}).json()
    assert updated["total"]==2 and all(item["record_type"]!="OBSERVATION" for item in updated["items"])


def test_report_contains_real_records_metrics_missing_states_and_snapshots(authenticated_client):
    child=create_child(authenticated_client); seed_records(child["id"])
    report=authenticated_client.get(f"/api/children/{child['id']}/report").json()
    assert report["counts"]=={"video":1,"observation":1,"activity":1}
    assert report["videos"][0]["sampled_frames"]==13 and report["videos"][0]["pose_coverage"]==0.8
    assert report["observations"][0]["observation_data"]["responds_to_name"]=="UNABLE_TO_JUDGE"
    assert report["activities"][0]["activity_name"]=="历史活动快照"
    assert report["activities"][0]["actual_duration_minutes"] is None
    text=json.dumps(report,ensure_ascii=False)
    assert "医学诊断" in report["disclaimer"] and "风险评分" not in text and "康复指数" not in text
    assert "<script>不会作为 HTML 执行</script>" in text


def test_report_type_and_date_filters_and_child_isolation(authenticated_client):
    first=create_child(authenticated_client,"报告儿童一"); second=create_child(authenticated_client,"报告儿童二")
    old=date.today()-timedelta(days=10); seed_records(first["id"],old); seed_records(first["id"]); seed_records(second["id"])
    only_observation=authenticated_client.get(f"/api/children/{first['id']}/report",params={"record_types":"OBSERVATION","start_date":date.today().isoformat()}).json()
    assert only_observation["counts"]=={"video":0,"observation":1,"activity":0}
    assert only_observation["observations"][0]["child_id"]==first["id"]


def test_failed_video_has_no_invented_report_metrics(authenticated_client):
    child=create_child(authenticated_client)
    with SessionLocal() as db:
        item=VideoAnalysis(child_id=child["id"],original_filename="failed.mp4",stored_filename="failed-report.mp4",file_path="private",file_sha256="f"*64,file_size=1,duration_seconds=1,width=100,height=100,source_fps=10,status="FAILED",error_message="可控失败")
        db.add(item); db.commit()
    report=authenticated_client.get(f"/api/children/{child['id']}/report",params={"record_types":"VIDEO"}).json()
    video=report["videos"][0]
    assert video["status"]=="FAILED" and video["sampled_frames"] is None and video["pose_coverage"] is None
