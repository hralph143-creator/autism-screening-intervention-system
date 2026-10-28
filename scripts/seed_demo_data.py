"""写入八套明确标识的演示案例，并对非真人合成视频执行真实分析。"""

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
        "history_offset_days": 5,
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
        "history_offset_days": 18,
    },
    {
        "code": "DEMO-CHILD-003",
        "nickname": "演示档案三（非真实儿童）",
        "birth_month": "2019-08",
        "gender": "男",
        "scene": "学习活动",
        "observer": "教师",
        "values": ("SOMETIMES", "NOT_SEEN_THIS_TIME", "OFTEN"),
        "activity_codes": ("ACT-ATT-001", "ACT-COM-002", "ACT-SOC-003"),
        "statuses": ("COMPLETED", "COMPLETED", "PARTIAL"),
        "history_offset_days": 32,
    },
    {
        "code": "DEMO-CHILD-004",
        "nickname": "演示档案四（非真实儿童）",
        "birth_month": "2022-02",
        "gender": "女",
        "scene": "用餐时段",
        "observer": "家长",
        "values": ("NOT_OBSERVED", "SOMETIMES", "UNABLE_TO_JUDGE"),
        "activity_codes": ("ACT-LIF-003", "ACT-ATT-002", "ACT-COM-003"),
        "statuses": ("PARTIAL", "NOT_COMPLETED", "COMPLETED"),
        "history_offset_days": 48,
    },
    {
        "code": "DEMO-CHILD-005",
        "nickname": "演示档案五（非真实儿童）",
        "birth_month": "2020-12",
        "gender": "未说明",
        "scene": "外出活动",
        "observer": "其他监护人",
        "values": ("OFTEN", "UNABLE_TO_JUDGE", "SOMETIMES"),
        "activity_codes": ("ACT-SOC-001", "ACT-ATT-003", "ACT-LIF-002"),
        "statuses": ("COMPLETED", "PARTIAL", "COMPLETED"),
        "history_offset_days": 65,
    },
    {
        "code": "DEMO-CHILD-006",
        "nickname": "演示档案六（非真实儿童）",
        "birth_month": "2018-06",
        "gender": "男",
        "scene": "家庭日常",
        "observer": "专业人员",
        "values": ("NOT_SEEN_THIS_TIME", "OFTEN", "SOMETIMES"),
        "activity_codes": ("ACT-COM-001", "ACT-SOC-002", "ACT-ATT-001"),
        "statuses": ("PARTIAL", "COMPLETED", "COMPLETED"),
        "history_offset_days": 82,
    },
    {
        "code": "DEMO-CHILD-007",
        "nickname": "演示档案七（非真实儿童）",
        "birth_month": "2021-03",
        "gender": "女",
        "scene": "游戏活动",
        "observer": "教师",
        "values": ("SOMETIMES", "NOT_OBSERVED", "OFTEN"),
        "activity_codes": ("ACT-LIF-001", "ACT-COM-003", "ACT-SOC-003"),
        "statuses": ("NOT_COMPLETED", "PARTIAL", "COMPLETED"),
        "history_offset_days": 101,
    },
    {
        "code": "DEMO-CHILD-008",
        "nickname": "演示档案八（非真实儿童）",
        "birth_month": "2019-01",
        "gender": "未说明",
        "scene": "其他",
        "observer": "其他观察者",
        "values": ("UNABLE_TO_JUDGE", "SOMETIMES", "NOT_SEEN_THIS_TIME"),
        "activity_codes": ("ACT-ATT-002", "ACT-LIF-003", "ACT-COM-002"),
        "statuses": ("COMPLETED", "PARTIAL", "NOT_COMPLETED"),
        "history_offset_days": 126,
    },
)

DEMO_DEVELOPMENT_NOTE = "演示数据：用于展示档案、视频、观察和家庭互动记录的完整流程，不对应真实儿童。"
DEMO_GUARDIAN_NOTE = "演示数据，可在体验完成后删除。"


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
        if (
            child.nickname != definition["nickname"]
            or child.development_notes != DEMO_DEVELOPMENT_NOTE
            or child.guardian_notes != DEMO_GUARDIAN_NOTE
        ):
            raise RuntimeError(
                f"儿童编号 {definition['code']} 已被非演示档案占用；为避免误关联，未写入任何关联记录。"
            )
        return child
    child = Child(
        child_code=definition["code"],
        nickname=definition["nickname"],
        birth_month=definition["birth_month"],
        gender=definition["gender"],
        development_notes=DEMO_DEVELOPMENT_NOTE,
        guardian_notes=DEMO_GUARDIAN_NOTE,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


def ensure_video(db, child: Child, set_number: int, temp_dir: Path, history_offset_days: int) -> VideoAnalysis:
    original_name = f"演示数据集{set_number}_非真人合成视频.mp4"
    existing = db.scalar(
        select(VideoAnalysis).where(
            VideoAnalysis.child_id == child.id,
            VideoAnalysis.original_filename == original_name,
        )
    )
    demo_time = datetime.utcnow() - timedelta(days=history_offset_days)
    if existing:
        if existing.status != "COMPLETED":
            raise RuntimeError(
                f"演示视频记录 #{existing.id} 状态为 {existing.status}；为避免生成重复记录，请先检查该任务。"
            )
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
        created_at=demo_time,
        started_at=demo_time,
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
    record.completed_at = demo_time
    db.commit()
    db.refresh(record)
    return record


def ensure_observations(db, child: Child, video: VideoAnalysis, definition: dict, set_number: int) -> list[ObservationRecord]:
    records = []
    options = definition["values"]
    for record_number in (1, 2):
        marker = f"演示案例{set_number}-观察{record_number}：非真实儿童数据。"
        existing = db.scalar(
            select(ObservationRecord).where(
                ObservationRecord.child_id == child.id,
                ObservationRecord.summary_notes == marker,
            )
        )
        if existing:
            records.append(existing)
            continue
        observation_data = {
            key: options[(index + record_number - 1) % len(options)] for index, key in enumerate(ITEMS)
        }
        record = ObservationRecord(
            child_id=child.id,
            video_analysis_id=video.id if record_number == 1 else None,
            observation_date=date.today() - timedelta(
                days=definition["history_offset_days"] + (record_number - 1) * 14
            ),
            observation_scene=definition["scene"],
            observer_role=definition["observer"],
            observation_data=json.dumps(observation_data, ensure_ascii=False, sort_keys=True),
            summary_notes=marker,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        records.append(record)
    return records


def ensure_activity_records(db, child: Child, definition: dict, set_number: int) -> list[ActivityRecord]:
    records = []
    for index, (code, completion_status) in enumerate(zip(definition["activity_codes"], definition["statuses"])):
        activity = db.scalar(select(Activity).where(Activity.activity_code == code))
        if not activity:
            raise RuntimeError(f"缺少内置活动：{code}")
        response_marker = f"演示数据集{set_number}：用于展示“{activity.name}”活动记录流程，不对应真实儿童表现。"
        existing = db.scalar(
            select(ActivityRecord).where(
                ActivityRecord.child_id == child.id,
                ActivityRecord.activity_id == activity.id,
                ActivityRecord.child_response == response_marker,
            )
        )
        if existing:
            records.append(existing)
            continue
        activity_date = date.today() - timedelta(days=definition["history_offset_days"] + index * 9)
        record = ActivityRecord(
            child_id=child.id,
            activity_id=activity.id,
            activity_date=activity_date,
            completion_status=completion_status,
            actual_duration_minutes=None if completion_status == "NOT_COMPLETED" else activity.suggested_duration_minutes,
            child_response=response_marker,
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
            video = ensure_video(db, child, set_number, temp_dir, definition["history_offset_days"])
            observations = ensure_observations(db, child, video, definition, set_number)
            activities = ensure_activity_records(db, child, definition, set_number)
            summary.append(
                {
                    "dataset": set_number,
                    "child_code": child.child_code,
                    "video_id": video.id,
                    "video_status": video.status,
                    "observation_records": len(observations),
                    "activity_records": len(activities),
                }
            )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
