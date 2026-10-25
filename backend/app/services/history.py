from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.orm import Session

from ..models.activity import ActivityRecord
from ..models.child import Child
from ..models.observation import ObservationRecord
from ..models.video_analysis import VideoAnalysis
from .activities import COMPLETION_LABELS, record_to_dict
from .children import child_to_dict
from .observations import observation_to_dict

RECORD_TYPES = ("VIDEO", "OBSERVATION", "ACTIVITY")
RECORD_TYPE_LABELS = {"VIDEO": "视频分析", "OBSERVATION": "行为观察", "ACTIVITY": "家庭互动"}
VIDEO_STATUS_LABELS = {
    "PENDING": "等待中", "RUNNING": "分析中", "COMPLETED": "已完成",
    "FAILED": "失败", "INTERRUPTED": "已中断",
}
REPORT_LIMIT = 200
REPORT_DISCLAIMER = (
    "本报告由系统根据已保存的视频分析、行为观察和家庭活动记录整理生成，仅用于日常行为信息归档与辅助观察，"
    "不构成医学诊断、标准化筛查结果或治疗建议。如对儿童发育情况存在疑虑，请咨询相关专业人员。"
)


def validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise ValueError("开始日期不能晚于结束日期")


def child_overview(db: Session, child: Child) -> dict:
    video_count = int(db.scalar(select(func.count(VideoAnalysis.id)).where(VideoAnalysis.child_id == child.id)) or 0)
    observation_count = int(db.scalar(select(func.count(ObservationRecord.id)).where(ObservationRecord.child_id == child.id)) or 0)
    activity_count = int(db.scalar(select(func.count(ActivityRecord.id)).where(ActivityRecord.child_id == child.id)) or 0)
    latest_candidates = [
        db.scalar(select(func.max(func.date(VideoAnalysis.created_at))).where(VideoAnalysis.child_id == child.id)),
        db.scalar(select(func.max(ObservationRecord.observation_date)).where(ObservationRecord.child_id == child.id)),
        db.scalar(select(func.max(ActivityRecord.activity_date)).where(ActivityRecord.child_id == child.id)),
    ]
    latest = max((str(value) for value in latest_candidates if value), default=None)

    monthly: dict[str, dict[str, int]] = defaultdict(lambda: {key: 0 for key in RECORD_TYPES})
    video_month = func.strftime("%Y-%m", func.date(VideoAnalysis.created_at))
    for month, count in db.execute(
        select(video_month, func.count(VideoAnalysis.id))
        .where(VideoAnalysis.child_id == child.id).group_by(video_month)
    ):
        if month: monthly[str(month)]["VIDEO"] = int(count)
    observation_month = func.strftime("%Y-%m", ObservationRecord.observation_date)
    for month, count in db.execute(
        select(observation_month, func.count(ObservationRecord.id))
        .where(ObservationRecord.child_id == child.id).group_by(observation_month)
    ):
        if month: monthly[str(month)]["OBSERVATION"] = int(count)
    activity_month = func.strftime("%Y-%m", ActivityRecord.activity_date)
    for month, count in db.execute(
        select(activity_month, func.count(ActivityRecord.id))
        .where(ActivityRecord.child_id == child.id).group_by(activity_month)
    ):
        if month: monthly[str(month)]["ACTIVITY"] = int(count)

    video_status_counts = dict(db.execute(
        select(VideoAnalysis.status, func.count(VideoAnalysis.id))
        .where(VideoAnalysis.child_id == child.id).group_by(VideoAnalysis.status)
    ).all())
    activity_categories = dict(db.execute(
        select(ActivityRecord.category_snapshot, func.count(ActivityRecord.id))
        .where(ActivityRecord.child_id == child.id).group_by(ActivityRecord.category_snapshot)
    ).all())
    return {
        "child": child_to_dict(child),
        "counts": {"video": video_count, "observation": observation_count, "activity": activity_count},
        "latest_record_date": latest,
        "monthly_counts": [{"month": month, **counts} for month, counts in sorted(monthly.items())],
        "video_status_counts": {key: int(value) for key, value in video_status_counts.items()},
        "activity_category_counts": {key: int(value) for key, value in activity_categories.items()},
    }


def timeline_query(
    db: Session, child_id: int, record_type: str | None, start_date: date | None,
    end_date: date | None, page: int, page_size: int, sort_order: str,
) -> dict:
    statements = []
    selected = (record_type,) if record_type else RECORD_TYPES
    if "VIDEO" in selected:
        filters = [VideoAnalysis.child_id == child_id]
        if start_date: filters.append(func.date(VideoAnalysis.created_at) >= start_date)
        if end_date: filters.append(func.date(VideoAnalysis.created_at) <= end_date)
        statements.append(select(
            literal("VIDEO").label("record_type"), VideoAnalysis.id.label("record_id"),
            func.date(VideoAnalysis.created_at).label("business_date"), VideoAnalysis.created_at.label("created_at"),
            VideoAnalysis.original_filename.label("title"), VideoAnalysis.status.label("status"),
        ).where(*filters))
    if "OBSERVATION" in selected:
        filters = [ObservationRecord.child_id == child_id]
        if start_date: filters.append(ObservationRecord.observation_date >= start_date)
        if end_date: filters.append(ObservationRecord.observation_date <= end_date)
        statements.append(select(
            literal("OBSERVATION").label("record_type"), ObservationRecord.id.label("record_id"),
            ObservationRecord.observation_date.label("business_date"), ObservationRecord.created_at.label("created_at"),
            ObservationRecord.observation_scene.label("title"), literal("RECORDED").label("status"),
        ).where(*filters))
    if "ACTIVITY" in selected:
        filters = [ActivityRecord.child_id == child_id]
        if start_date: filters.append(ActivityRecord.activity_date >= start_date)
        if end_date: filters.append(ActivityRecord.activity_date <= end_date)
        statements.append(select(
            literal("ACTIVITY").label("record_type"), ActivityRecord.id.label("record_id"),
            ActivityRecord.activity_date.label("business_date"), ActivityRecord.created_at.label("created_at"),
            ActivityRecord.activity_name_snapshot.label("title"), ActivityRecord.completion_status.label("status"),
        ).where(*filters))
    combined = union_all(*statements).subquery()
    total = int(db.scalar(select(func.count()).select_from(combined)) or 0)
    date_order = combined.c.business_date.asc() if sort_order == "asc" else combined.c.business_date.desc()
    created_order = combined.c.created_at.asc() if sort_order == "asc" else combined.c.created_at.desc()
    rows = db.execute(
        select(combined).order_by(date_order, created_order, combined.c.record_type.asc(), combined.c.record_id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).mappings().all()
    items = []
    for row in rows:
        kind = str(row["record_type"])
        status_value = str(row["status"])
        status_label = (
            VIDEO_STATUS_LABELS.get(status_value, status_value) if kind == "VIDEO"
            else "已记录" if kind == "OBSERVATION" else COMPLETION_LABELS.get(status_value, status_value)
        )
        items.append({
            "record_type": kind, "record_type_label": RECORD_TYPE_LABELS[kind], "record_id": int(row["record_id"]),
            "business_date": str(row["business_date"]),
            "date_meaning": "任务创建日期" if kind == "VIDEO" else "观察日期" if kind == "OBSERVATION" else "活动日期",
            "title": str(row["title"]), "status": status_value, "status_label": status_label,
            "detail_path": "/analysis" if kind == "VIDEO" else "/observations" if kind == "OBSERVATION" else "/activities",
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size, "sort_order": sort_order}


def _video_report_item(record: VideoAnalysis) -> dict:
    summary = None
    motion = None
    if record.status == "COMPLETED" and record.result_json:
        try:
            result = json.loads(record.result_json)
            summary = result.get("summary")
            motion = result.get("motion_statistics")
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": record.id, "video_name": record.original_filename, "analysis_date": record.created_at.date(),
        "duration_seconds": record.duration_seconds, "status": record.status,
        "status_label": VIDEO_STATUS_LABELS.get(record.status, record.status),
        "error_message": "分析任务未完成，请在视频分析模块查看原因" if record.error_message else None,
        "sampled_frames": summary.get("sampled_frames") if summary else None,
        "pose_coverage": summary.get("pose_coverage") if summary else None,
        "face_coverage": summary.get("face_coverage") if summary else None,
        "quality_level": summary.get("quality_level") if summary else None,
        "motion_statistics": motion,
    }


def build_report(
    db: Session, child: Child, start_date: date | None, end_date: date | None, included_types: tuple[str, ...],
) -> dict:
    candidates: list[tuple[date, str, object]] = []
    if "VIDEO" in included_types:
        filters = [VideoAnalysis.child_id == child.id]
        if start_date: filters.append(func.date(VideoAnalysis.created_at) >= start_date)
        if end_date: filters.append(func.date(VideoAnalysis.created_at) <= end_date)
        for item in db.scalars(select(VideoAnalysis).where(*filters).order_by(VideoAnalysis.created_at.desc(), VideoAnalysis.id.desc()).limit(REPORT_LIMIT + 1)):
            candidates.append((item.created_at.date(), "VIDEO", item))
    if "OBSERVATION" in included_types:
        filters = [ObservationRecord.child_id == child.id]
        if start_date: filters.append(ObservationRecord.observation_date >= start_date)
        if end_date: filters.append(ObservationRecord.observation_date <= end_date)
        for item in db.scalars(select(ObservationRecord).where(*filters).order_by(ObservationRecord.observation_date.desc(), ObservationRecord.id.desc()).limit(REPORT_LIMIT + 1)):
            candidates.append((item.observation_date, "OBSERVATION", item))
    if "ACTIVITY" in included_types:
        filters = [ActivityRecord.child_id == child.id]
        if start_date: filters.append(ActivityRecord.activity_date >= start_date)
        if end_date: filters.append(ActivityRecord.activity_date <= end_date)
        for item in db.scalars(select(ActivityRecord).where(*filters).order_by(ActivityRecord.activity_date.desc(), ActivityRecord.id.desc()).limit(REPORT_LIMIT + 1)):
            candidates.append((item.activity_date, "ACTIVITY", item))
    candidates.sort(key=lambda item: (item[0], item[1], getattr(item[2], "id")), reverse=True)
    truncated = len(candidates) > REPORT_LIMIT
    candidates = candidates[:REPORT_LIMIT]
    videos = [_video_report_item(item) for _, kind, item in candidates if kind == "VIDEO"]
    observations = [observation_to_dict(item, db) for _, kind, item in candidates if kind == "OBSERVATION"]
    activities = [record_to_dict(item, db) for _, kind, item in candidates if kind == "ACTIVITY"]
    dates = [item[0] for item in candidates]
    pending_videos = sum(item["status"] in ("PENDING", "RUNNING", "INTERRUPTED") for item in videos)
    missing_observation_items = sum(item["data_completeness"]["unfilled_items"] for item in observations)
    missing_activity_durations = sum(item["actual_duration_minutes"] is None for item in activities)
    counts = {"video": len(videos), "observation": len(observations), "activity": len(activities)}
    explanation = [f"本次报告共纳入 {sum(counts.values())} 条记录。"]
    if dates: explanation.append(f"记录覆盖 {min(dates).isoformat()} 至 {max(dates).isoformat()}。")
    else: explanation.append("所选范围内暂无相关记录。")
    explanation.extend([
        f"存在 {pending_videos} 条尚未形成完整结果的视频任务。",
        f"行为观察中共有 {missing_observation_items} 个项目未填写。",
        f"家庭活动中有 {missing_activity_durations} 条未填写实际时长。",
    ])
    if truncated: explanation.append(f"记录超过上限，本报告仅纳入按业务日期倒序排列的前 {REPORT_LIMIT} 条。")
    return {
        "title": "儿童行为观察与活动记录综合报告", "generated_at": datetime.now(),
        "requested_range": {"start_date": start_date, "end_date": end_date},
        "actual_range": {"start_date": min(dates) if dates else None, "end_date": max(dates) if dates else None},
        "included_types": list(included_types), "record_limit": REPORT_LIMIT, "truncated": truncated,
        "child": child_to_dict(child), "counts": counts,
        "videos": videos, "observations": observations, "activities": activities,
        "record_explanation": explanation, "disclaimer": REPORT_DISCLAIMER,
    }
