"""写入两套明确标识的演示数据，并对非真人合成视频执行真实分析。"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, initialize_database
from backend.app.models.activity import Activity, ActivityRecord
from backend.app.models.child import Child
from backend.app.models.observation import ObservationRecord
from backend.app.models.video_analysis import VideoAnalysis
from backend.app.services.model_manager import model_status
from backend.app.services.observation_definition import ITEMS
from backend.app.services.video_analyzer import analyze_video
from backend.app.services.video_files import inspect_video


DEMO_SETS = (
    {
        "code": "DEMO-CHILD-001",
        "nickname": "演示档案一（非真实儿童）",
        "birth_month": "2020-05",
        "gender": "男",
        "scene": "游戏活动",
        "observer": "家长",
        "values": ("OFTEN", "SOMETIMES", "NOT_SEEN_THIS_TIME"),
        "activity_codes": ("ACT-SOC-001", "ACT-COM-001", "ACT-LIF-001"),
        "statuses": ("COMPLETED", "PARTIAL", "COMPLETED"),
    },
    {
        "code": "DEMO-CHILD-002",
        "nickname": "演示档案二（非真实儿童）",
        "birth_month": "2021-11",
        "gender": "女",
        "scene": "家庭日常",
        "observer": "其他监护人",
        "values": ("SOMETIMES", "OFTEN", "UNABLE_TO_JUDGE"),
        "activity_codes": ("ACT-SOC-002", "ACT-ATT-001", "ACT-LIF-002"),
        "statuses": ("PARTIAL", "COMPLETED", "NOT_COMPLETED"),
    },
)


def create_synthetic_video(target: Path, label: str) -> None:
    """生成不含真人、可明确识别为演示素材的短 MP4。"""
    width, height, fps, frames = 640, 360, 15.0, 60
    writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("无法创建演示 MP4，请检查 OpenCV 视频编码支持")
    try:
        for index in range(frames):
            frame = np.full((height, width, 3), (242, 247, 246), dtype=np.uint8)
            x = 90 + int(index * 7.2)
            cv2.circle(frame, (x, 190), 34, (42, 137, 141), -1, cv2.LINE_AA)
            cv2.rectangle(frame, (70, 260), (570, 280), (208, 220, 218), -1)
            cv2.putText(frame, "SYNTHETIC DEMO - NO REAL PERSON", (98, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (45, 74, 76), 2, cv2.LINE_AA)
            cv2.putText(frame, label, (255, 325), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 98, 100), 2, cv2.LINE_AA)
            writer.write(frame)
    finally:
        writer.release()


def ensure_child(db, definition: dict) -> Child:
    child = db.scalar(select(Child).where(Child.child_code == definition["code"]))
    if child:
        return child
    child = Child(
        child_code=definition["code"],
        nickname=definition["nickname"],
        birth_month=definition["birth_month"],
        gender=definition["gender"],
        development_notes="演示数据：用于展示档案、视频、观察和家庭互动记录的完整流程，不对应真实儿童。",
        guardian_notes="演示数据，可在体验完成后删除。",
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


def ensure_video(db, child: Child, set_number: int, temp_dir: Path) -> VideoAnalysis:
    original_name = f"演示数据集{set_number}_非真人合成视频.mp4"
    existing = db.scalar(
        select(VideoAnalysis).where(
            VideoAnalysis.child_id == child.id,
            VideoAnalysis.original_filename == original_name,
            VideoAnalysis.status == "COMPLETED",
        )
    )
    if existing:
        return existing

    source = temp_dir / f"demo_{set_number}.mp4"
    create_synthetic_video(source, f"DEMO SET {set_number}")
    stored_name = f"{uuid.uuid4().hex}.mp4"
    destination = settings.upload_dir / stored_name
    shutil.copyfile(source, destination)
    metadata = inspect_video(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    record = VideoAnalysis(
        child_id=child.id,
        original_filename=original_name,
        stored_filename=stored_name,
        file_path=str(destination.resolve()),
        file_sha256=digest,
        file_size=destination.stat().st_size,
        duration_seconds=float(metadata["duration_seconds"]),
        width=int(metadata["width"]),
        height=int(metadata["height"]),
        source_fps=float(metadata["source_fps"]),
        status="RUNNING",
        progress=2,
        started_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    result_dir = settings.analysis_result_dir / str(record.id)
    try:
        result = analyze_video(
            destination,
            result_dir,
            {"source_fps": record.source_fps, "frame_count": round(record.duration_seconds * record.source_fps)},
        )
    except Exception as exc:
        record.status = "FAILED"
        record.progress = 0
        record.error_message = f"演示视频分析失败：{type(exc).__name__}: {str(exc)[:400]}"
        record.completed_at = datetime.utcnow()
        db.commit()
        raise
    record.status = "COMPLETED"
    record.progress = 100
    record.result_json = json.dumps(result, ensure_ascii=False)
    record.result_dir = str(result_dir.resolve())
    record.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def ensure_observation(db, child: Child, video: VideoAnalysis, definition: dict, set_number: int) -> ObservationRecord:
    marker = f"演示数据集{set_number}：本记录仅用于界面和流程展示，不代表真实儿童观察结论。"
    existing = db.scalar(
        select(ObservationRecord).where(
            ObservationRecord.child_id == child.id,
            ObservationRecord.summary_notes == marker,
        )
    )
    if existing:
        return existing
    options = definition["values"]
    observation_data = {key: options[index % len(options)] for index, key in enumerate(ITEMS)}
    record = ObservationRecord(
        child_id=child.id,
        video_analysis_id=video.id,
        observation_date=date.today() - timedelta(days=6 - set_number),
        observation_scene=definition["scene"],
        observer_role=definition["observer"],
        observation_data=json.dumps(observation_data, ensure_ascii=False, sort_keys=True),
        summary_notes=marker,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def ensure_activity_records(db, child: Child, definition: dict, set_number: int) -> list[ActivityRecord]:
    records = []
    for index, (code, completion_status) in enumerate(zip(definition["activity_codes"], definition["statuses"])):
        activity = db.scalar(select(Activity).where(Activity.activity_code == code))
        if not activity:
            raise RuntimeError(f"缺少内置活动：{code}")
        activity_date = date.today() - timedelta(days=(index + 1) * 2 + set_number)
        existing = db.scalar(
            select(ActivityRecord).where(
                ActivityRecord.child_id == child.id,
                ActivityRecord.activity_id == activity.id,
                ActivityRecord.activity_date == activity_date,
            )
        )
        if existing:
            records.append(existing)
            continue
        record = ActivityRecord(
            child_id=child.id,
            activity_id=activity.id,
            activity_date=activity_date,
            completion_status=completion_status,
            actual_duration_minutes=None if completion_status == "NOT_COMPLETED" else activity.suggested_duration_minutes,
            child_response=f"演示数据集{set_number}：用于展示“{activity.name}”活动记录流程，不对应真实儿童表现。",
            notes="演示记录，可删除；不用于疾病判断或效果评价。",
            activity_code_snapshot=activity.activity_code,
            activity_name_snapshot=activity.name,
            category_snapshot=activity.category,
            objective_snapshot=activity.objective,
            suggested_duration_snapshot=activity.suggested_duration_minutes,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        records.append(record)
    return records


def main() -> None:
    initialize_database()
    readiness = model_status(validate_load=True)
    if not readiness["ready"]:
        raise SystemExit(f"视频模型不可用，未写入不完整演示数据：{readiness['error']}")
    summary = []
    with tempfile.TemporaryDirectory(prefix="autism_demo_") as temp_name, SessionLocal() as db:
        temp_dir = Path(temp_name)
        for set_number, definition in enumerate(DEMO_SETS, start=1):
            child = ensure_child(db, definition)
            video = ensure_video(db, child, set_number, temp_dir)
            observation = ensure_observation(db, child, video, definition, set_number)
            activities = ensure_activity_records(db, child, definition, set_number)
            summary.append(
                {
                    "dataset": set_number,
                    "child_code": child.child_code,
                    "video_id": video.id,
                    "video_status": video.status,
                    "observation_id": observation.id,
                    "activity_records": len(activities),
                }
            )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
