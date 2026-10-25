import io
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.child import Child
from backend.app.models.video_analysis import VideoAnalysis
from backend.app.services.analysis_queue import analysis_queue
from backend.app.services.model_manager import model_status
from backend.app.services.video_analyzer import _quality_level, _sampling_plan, analyze_video
from backend.app.services.video_files import inspect_video


def create_child(client) -> dict:
    response = client.post("/api/children", json={"nickname": "视频测试档案"})
    assert response.status_code == 201
    return response.json()


def make_mp4(tmp_path: Path, seconds: float = 1.0) -> bytes:
    path = tmp_path / "valid.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    assert writer.isOpened()
    for index in range(round(seconds * 10)):
        frame = np.full((120, 160, 3), (index * 12) % 255, dtype=np.uint8)
        cv2.rectangle(frame, (40 + index, 30), (110, 105), (20, 180, 220), -1)
        writer.write(frame)
    writer.release()
    return path.read_bytes()


def ready_status(*_args, **_kwargs):
    return {"ready": True, "error": None}


def test_short_video_sampling_is_adaptive():
    frame_step, sampled_total, effective_fps = _sampling_plan(100, 76)
    assert frame_step == 9
    assert sampled_total == 9
    assert effective_fps > settings.analysis_sample_fps

    long_step, long_total, long_effective_fps = _sampling_plan(30, 300)
    assert long_step == 15
    assert long_total == 20
    assert long_effective_fps == settings.analysis_sample_fps


def test_quality_level_reports_partial_detection():
    assert _quality_level(1.0, 0.0) == "部分数据可用"
    assert _quality_level(0.8, 0.8) == "良好"
    assert _quality_level(0.0, 0.0) == "有效数据不足"


def test_video_routes_require_authentication(client):
    assert client.get("/api/models/status").status_code == 401
    assert client.get("/api/video-analyses").status_code == 401


def test_model_status_performs_real_load_when_models_installed(authenticated_client):
    result = authenticated_client.get("/api/models/status")
    assert result.status_code == 200
    payload = result.json()
    if settings.pose_model_path.exists() and settings.face_model_path.exists():
        assert payload["ready"] is True
        assert payload["models"]["pose"]["loadable"] is True
        assert payload["models"]["face"]["loadable"] is True


def test_upload_requires_consent_and_real_mp4(authenticated_client, monkeypatch, tmp_path):
    child = create_child(authenticated_client)
    monkeypatch.setattr("backend.app.api.video_analyses.model_status", ready_status)
    response = authenticated_client.post(
        "/api/video-analyses",
        data={"child_id": child["id"], "consent_confirmed": "false"},
        files={"file": ("clip.mp4", io.BytesIO(make_mp4(tmp_path)), "video/mp4")},
    )
    assert response.status_code == 422
    empty = authenticated_client.post(
        "/api/video-analyses",
        data={"child_id": child["id"], "consent_confirmed": "true"},
        files={"file": ("empty.mp4", io.BytesIO(b""), "video/mp4")},
    )
    assert empty.status_code == 422 and "为空" in empty.json()["detail"]
    missing_child = authenticated_client.post(
        "/api/video-analyses",
        data={"child_id": 999999, "consent_confirmed": "true"},
        files={"file": ("clip.mp4", io.BytesIO(make_mp4(tmp_path)), "video/mp4")},
    )
    assert missing_child.status_code == 404
    fake = authenticated_client.post(
        "/api/video-analyses",
        data={"child_id": child["id"], "consent_confirmed": "true"},
        files={"file": ("fake.mp4", io.BytesIO(b"not a video"), "video/mp4")},
    )
    assert fake.status_code == 422
    assert "有效的 MP4" in fake.json()["detail"]


def test_model_unavailable_is_explicit(authenticated_client, monkeypatch, tmp_path):
    child = create_child(authenticated_client)
    monkeypatch.setattr("backend.app.api.video_analyses.model_status", lambda **_: {"ready": False, "error": "模型测试性缺失"})
    response = authenticated_client.post(
        "/api/video-analyses",
        data={"child_id": child["id"], "consent_confirmed": "true"},
        files={"file": ("clip.mp4", io.BytesIO(make_mp4(tmp_path)), "video/mp4")},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "模型测试性缺失"


def test_upload_rejects_oversize_and_too_long(authenticated_client, monkeypatch, tmp_path):
    child = create_child(authenticated_client)
    monkeypatch.setattr("backend.app.api.video_analyses.model_status", ready_status)
    original_bytes, original_seconds = settings.max_video_bytes, settings.max_video_seconds
    try:
        object.__setattr__(settings, "max_video_bytes", 100)
        oversized = authenticated_client.post(
            "/api/video-analyses",
            data={"child_id": child["id"], "consent_confirmed": "true"},
            files={"file": ("large.mp4", io.BytesIO(make_mp4(tmp_path)), "video/mp4")},
        )
        assert oversized.status_code == 413
        object.__setattr__(settings, "max_video_bytes", original_bytes)
        object.__setattr__(settings, "max_video_seconds", 0.3)
        too_long = authenticated_client.post(
            "/api/video-analyses",
            data={"child_id": child["id"], "consent_confirmed": "true"},
            files={"file": ("long.mp4", io.BytesIO(make_mp4(tmp_path, 1)), "video/mp4")},
        )
        assert too_long.status_code == 422
        assert "时长" in too_long.json()["detail"]
    finally:
        object.__setattr__(settings, "max_video_bytes", original_bytes)
        object.__setattr__(settings, "max_video_seconds", original_seconds)


def test_upload_duplicate_list_and_delete(authenticated_client, monkeypatch, tmp_path):
    child = create_child(authenticated_client)
    content = make_mp4(tmp_path)
    monkeypatch.setattr("backend.app.api.video_analyses.model_status", ready_status)
    enqueued = []
    monkeypatch.setattr(analysis_queue, "enqueue", enqueued.append)
    response = authenticated_client.post(
        "/api/video-analyses",
        data={"child_id": child["id"], "consent_confirmed": "true"},
        files={"file": ("clip.mp4", io.BytesIO(content), "video/mp4")},
    )
    assert response.status_code == 202
    task = response.json()
    assert task["status"] == "PENDING" and enqueued == [task["id"]]
    with SessionLocal() as db:
        saved = db.get(VideoAnalysis, task["id"])
        assert Path(saved.file_path).is_file()
        assert saved.stored_filename != "clip.mp4"
    duplicate = authenticated_client.post(
        "/api/video-analyses",
        data={"child_id": child["id"], "consent_confirmed": "true"},
        files={"file": ("copy.mp4", io.BytesIO(content), "video/mp4")},
    )
    assert duplicate.status_code == 409
    listing = authenticated_client.get("/api/video-analyses", params={"child_id": child["id"], "status": "PENDING"})
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert authenticated_client.delete(f"/api/video-analyses/{task['id']}").status_code == 409
    with SessionLocal() as db:
        saved = db.get(VideoAnalysis, task["id"]); saved.status = "FAILED"; saved_path = Path(saved.file_path); db.commit()
    assert authenticated_client.delete(f"/api/video-analyses/{task['id']}").status_code == 200
    assert not saved_path.exists()


def test_worker_success_failure_interruption_and_protected_frame(authenticated_client, monkeypatch, tmp_path):
    child = create_child(authenticated_client)
    source = tmp_path / "source.mp4"; source.write_bytes(make_mp4(tmp_path))
    with SessionLocal() as db:
        record = VideoAnalysis(child_id=child["id"], original_filename="source.mp4", stored_filename="worker.mp4", file_path=str(source), file_sha256="a"*64, file_size=source.stat().st_size, duration_seconds=1, width=160, height=120, source_fps=10)
        db.add(record); db.commit(); db.refresh(record); record_id = record.id
    sample_result = {"summary": {"quality_level": "有效数据不足"}, "preview_frames": [], "time_series": [], "warnings": [], "calculation_notes": [], "disclaimer": "仅为客观描述"}
    monkeypatch.setattr("backend.app.services.analysis_queue.analyze_video", lambda *_args, **_kwargs: sample_result)
    analysis_queue._process(record_id)
    result = authenticated_client.get(f"/api/video-analyses/{record_id}/result")
    assert result.status_code == 200 and result.json()["result"]["disclaimer"] == "仅为客观描述"

    frame_dir = settings.analysis_result_dir / str(record_id); frame_dir.mkdir(parents=True, exist_ok=True)
    (frame_dir / "frame_01.jpg").write_bytes(b"jpeg")
    with SessionLocal() as db:
        record = db.get(VideoAnalysis, record_id); record.result_dir = str(frame_dir); record.result_json = json.dumps({**sample_result, "preview_frames": [{"filename": "frame_01.jpg", "timestamp_ms": 0}]}, ensure_ascii=False); db.commit()
    assert authenticated_client.get(f"/api/video-analyses/{record_id}/frames/frame_01.jpg").status_code == 200
    assert authenticated_client.get(f"/api/video-analyses/{record_id}/frames/..%2Fsecret.jpg").status_code in (404, 422)
    monkeypatch.setattr("backend.app.api.video_analyses.model_status", ready_status)
    retried = []
    monkeypatch.setattr(analysis_queue, "enqueue", retried.append)
    retry_response = authenticated_client.post(f"/api/video-analyses/{record_id}/retry")
    assert retry_response.status_code == 202 and retry_response.json()["status"] == "PENDING"
    assert retried == [record_id] and not frame_dir.exists()

    with SessionLocal() as db:
        failed = VideoAnalysis(child_id=child["id"], original_filename="bad.mp4", stored_filename="failed.mp4", file_path=str(source), file_sha256="b"*64, file_size=1, duration_seconds=1, width=160, height=120, source_fps=10)
        stale = VideoAnalysis(child_id=child["id"], original_filename="stale.mp4", stored_filename="stale.mp4", file_path=str(source), file_sha256="c"*64, file_size=1, duration_seconds=1, width=160, height=120, source_fps=10, status="RUNNING")
        db.add_all([failed, stale]); db.commit(); failed_id = failed.id; stale_id = stale.id
    monkeypatch.setattr("backend.app.services.analysis_queue.analyze_video", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("可控失败")))
    analysis_queue._process(failed_id)
    assert analysis_queue.interrupt_stale_tasks() >= 1
    with SessionLocal() as db:
        assert db.get(VideoAnalysis, failed_id).status == "FAILED"
        assert "可控失败" in db.get(VideoAnalysis, failed_id).error_message
        assert db.get(VideoAnalysis, stale_id).status == "INTERRUPTED"


def test_multiple_people_are_reported_as_ambiguous(monkeypatch, tmp_path):
    video = tmp_path / "ambiguous.mp4"; video.write_bytes(make_mp4(tmp_path))
    landmarks = [SimpleNamespace(x=0.3 + index * 0.005, y=0.2 + index * 0.01, visibility=1.0, presence=1.0) for index in range(33)]
    class FakePose:
        def detect_for_video(self, _image, _timestamp): return SimpleNamespace(pose_landmarks=[landmarks, landmarks])
    class FakeFace:
        def detect_for_video(self, _image, _timestamp): return SimpleNamespace(face_landmarks=[])
    monkeypatch.setattr("backend.app.services.video_analyzer.create_landmarkers", lambda _stack: (FakePose(), FakeFace()))
    result = analyze_video(video, tmp_path / "multi-result", inspect_video(video))
    assert result["summary"]["multi_pose_frames"] == result["summary"]["sampled_frames"]
    assert any("多人" in warning for warning in result["warnings"])
    assert result["motion_statistics"]["head_location_change"]["valid_count"] == 0


def test_actual_models_handle_no_person_video_without_false_success(tmp_path):
    if not model_status(validate_load=False)["ready"]:
        pytest.skip("真实模型未安装")
    video = tmp_path / "blank.mp4"; video.write_bytes(make_mp4(tmp_path))
    result = analyze_video(video, tmp_path / "blank-result", inspect_video(video))
    assert result["summary"]["pose_valid_frames"] == 0
    assert result["summary"]["face_valid_frames"] == 0
    assert result["summary"]["quality_level"] == "有效数据不足"
    assert result["disclaimer"].startswith("本结果只描述")
    timestamps = [item["timestamp_ms"] for item in result["time_series"]]
    assert len(timestamps) == 10
    assert all(current > previous for previous, current in zip(timestamps, timestamps[1:]))
