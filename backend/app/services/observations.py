from __future__ import annotations

import json
from collections import Counter
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.child import Child
from ..models.observation import ObservationRecord
from ..models.video_analysis import VideoAnalysis
from .observation_definition import ITEMS, OBSERVATION_DIMENSIONS, OPTION_LABELS, form_definition


def parse_video_result(record: VideoAnalysis) -> int | None:
    if record.status != "COMPLETED" or not record.result_json:
        return None
    try:
        return int(json.loads(record.result_json).get("summary", {}).get("sampled_frames"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def query_observations(
    db: Session,
    child_id: int | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> tuple[list[ObservationRecord], int]:
    filters = []
    if child_id:
        filters.append(ObservationRecord.child_id == child_id)
    if date_from:
        filters.append(ObservationRecord.observation_date >= date_from)
    if date_to:
        filters.append(ObservationRecord.observation_date <= date_to)
    total = db.scalar(select(func.count(ObservationRecord.id)).where(*filters)) or 0
    records = list(
        db.scalars(
            select(ObservationRecord)
            .where(*filters)
            .order_by(ObservationRecord.observation_date.desc(), ObservationRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return records, total


def build_summary(record: ObservationRecord, data: dict[str, str]) -> tuple[str, dict]:
    dimensions = []
    for dimension in OBSERVATION_DIMENSIONS:
        if any(item["key"] in data for item in dimension["items"]):
            dimensions.append(dimension["label"])
    counts = Counter(data.values())
    total = len(ITEMS)
    sentences = [
        f"本次记录日期为{record.observation_date.isoformat()}，观察场景为{record.observation_scene}。",
        f"已记录{len(data)}/{total}个观察项目，涉及{'、'.join(dimensions) if dimensions else '尚未形成维度记录'}。",
    ]
    for option in ("OFTEN", "SOMETIMES", "NOT_SEEN_THIS_TIME"):
        labels = [ITEMS[key]["label"] for key, value in data.items() if value == option]
        if labels:
            shown = "、".join(labels[:3]) + (f"等{len(labels)}项" if len(labels) > 3 else "")
            sentences.append(f"{OPTION_LABELS[option]}的项目包括：{shown}。")
    pending = counts["UNABLE_TO_JUDGE"] + counts["NOT_OBSERVED"] + (total - len(data))
    if pending:
        sentences.append(
            f"有{counts['UNABLE_TO_JUDGE']}项无法判断、{counts['NOT_OBSERVED']}项明确标记为未观察，另有{total - len(data)}项未填写，建议在合适场景继续记录。"
        )
    if record.summary_notes:
        sentences.append("观察者另有补充说明，查看详情时可结合原始备注阅读。")
    completeness = {
        "total_items": total,
        "recorded_items": len(data),
        "unfilled_items": total - len(data),
        "unable_to_judge_items": counts["UNABLE_TO_JUDGE"],
        "not_observed_items": counts["NOT_OBSERVED"],
    }
    return "".join(sentences), completeness


def observation_to_dict(record: ObservationRecord, db: Session) -> dict:
    child = db.get(Child, record.child_id)
    data = json.loads(record.observation_data)
    summary, completeness = build_summary(record, data)
    video = db.get(VideoAnalysis, record.video_analysis_id) if record.video_analysis_id else None
    items = [
        {
            "key": key,
            "label": ITEMS[key]["label"],
            "dimension_key": ITEMS[key]["dimension_key"],
            "dimension_label": ITEMS[key]["dimension_label"],
            "value": value,
            "value_label": OPTION_LABELS[value],
        }
        for key, value in data.items()
    ]
    linked_video = None
    if video:
        linked_video = {
            "id": video.id,
            "original_filename": video.original_filename,
            "status": video.status,
            "created_at": video.created_at,
            "sampled_frames": parse_video_result(video),
        }
    return {
        "id": record.id,
        "child_id": record.child_id,
        "child_code": child.child_code if child else "已删除",
        "child_nickname": child.nickname if child else "已删除档案",
        "video_analysis_id": record.video_analysis_id,
        "linked_video": linked_video,
        "observation_date": record.observation_date,
        "observation_scene": record.observation_scene,
        "observer_role": record.observer_role,
        "observation_data": data,
        "observation_items": items,
        "summary_notes": record.summary_notes,
        "auxiliary_summary": summary,
        "data_completeness": completeness,
        "disclaimer": form_definition()["disclaimer"],
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
