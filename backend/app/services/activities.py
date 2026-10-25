from __future__ import annotations

import json
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.activity import Activity, ActivityRecord
from ..models.child import Child
from .builtin_activities import ACTIVITY_CATEGORIES, ACTIVITY_DISCLAIMER

COMPLETION_LABELS = {"COMPLETED": "已完成", "PARTIAL": "部分完成", "NOT_COMPLETED": "未完成"}


def age_in_months(birth_month: str, today: date | None = None) -> int:
    current = today or date.today()
    year, month = (int(part) for part in birth_month.split("-"))
    return max(0, (current.year - year) * 12 + current.month - month)


def activity_to_dict(activity: Activity) -> dict:
    return {
        "id": activity.id,
        "activity_code": activity.activity_code,
        "name": activity.name,
        "category": activity.category,
        "age_min_months": activity.age_min_months,
        "age_max_months": activity.age_max_months,
        "objective": activity.objective,
        "materials": json.loads(activity.materials),
        "steps": json.loads(activity.steps),
        "suggested_duration_minutes": activity.suggested_duration_minutes,
        "precautions": activity.precautions,
        "is_active": activity.is_active,
        "is_builtin": activity.is_builtin,
        "created_at": activity.created_at,
        "updated_at": activity.updated_at,
    }


def apply_activity_fields(activity: Activity, body) -> None:
    activity.name = body.name
    activity.category = body.category
    activity.age_min_months = body.age_min_months
    activity.age_max_months = body.age_max_months
    activity.objective = body.objective
    activity.materials = json.dumps(body.materials, ensure_ascii=False)
    activity.steps = json.dumps(body.steps, ensure_ascii=False)
    activity.suggested_duration_minutes = body.suggested_duration_minutes
    activity.precautions = body.precautions


def record_to_dict(record: ActivityRecord, db: Session) -> dict:
    child = db.get(Child, record.child_id)
    activity = db.get(Activity, record.activity_id)
    return {
        "id": record.id,
        "child_id": record.child_id,
        "child_code": child.child_code if child else "已删除",
        "child_nickname": child.nickname if child else "已删除档案",
        "activity_id": record.activity_id,
        "activity_code": record.activity_code_snapshot,
        "activity_name": record.activity_name_snapshot,
        "activity_category": record.category_snapshot,
        "activity_objective": record.objective_snapshot,
        "suggested_duration_minutes": record.suggested_duration_snapshot,
        "activity_date": record.activity_date,
        "completion_status": record.completion_status,
        "completion_label": COMPLETION_LABELS[record.completion_status],
        "actual_duration_minutes": record.actual_duration_minutes,
        "child_response": record.child_response,
        "notes": record.notes,
        "activity_is_active": bool(activity and activity.is_active),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "disclaimer": ACTIVITY_DISCLAIMER,
    }


def query_records(db: Session, child_id: int | None, category: str | None, date_from: date | None, date_to: date | None, page: int, page_size: int):
    filters = []
    if child_id:
        filters.append(ActivityRecord.child_id == child_id)
    if category:
        filters.append(ActivityRecord.category_snapshot == category)
    if date_from:
        filters.append(ActivityRecord.activity_date >= date_from)
    if date_to:
        filters.append(ActivityRecord.activity_date <= date_to)
    total = db.scalar(select(func.count(ActivityRecord.id)).where(*filters)) or 0
    records = list(db.scalars(select(ActivityRecord).where(*filters).order_by(ActivityRecord.activity_date.desc(), ActivityRecord.id.desc()).offset((page-1)*page_size).limit(page_size)).all())
    return records, total
