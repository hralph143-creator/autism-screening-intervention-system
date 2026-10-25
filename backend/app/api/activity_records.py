from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.activity import Activity, ActivityRecord
from ..models.child import Child
from ..schemas.activity import ActivityRecordInput, ActivityRecordListResponse, ActivityRecordResponse, ActivityStatsResponse
from ..services.activities import query_records, record_to_dict
from ..services.builtin_activities import ACTIVITY_CATEGORIES

router = APIRouter(prefix="/activity-records", tags=["家庭活动记录"], dependencies=[Depends(get_current_user)])


def get_record_or_404(record_id: int, db: Session) -> ActivityRecord:
    record = db.get(ActivityRecord, record_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "活动记录不存在")
    return record


def validate_filters(db: Session, child_id: int | None, category: str | None, date_from: date | None, date_to: date | None) -> None:
    if child_id and not db.get(Child, child_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    if category and category not in ACTIVITY_CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "活动分类不在允许范围内")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "开始日期不能晚于结束日期")


def validate_relations(body: ActivityRecordInput, db: Session, existing: ActivityRecord | None = None) -> tuple[Child, Activity]:
    child = db.get(Child, body.child_id)
    if not child:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    activity = db.get(Activity, body.activity_id)
    if not activity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "活动不存在")
    if not activity.is_active and (not existing or existing.activity_id != activity.id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "已停用活动不能用于新记录")
    return child, activity


def apply_record(
    record: ActivityRecord,
    body: ActivityRecordInput,
    activity: Activity,
    *,
    refresh_snapshot: bool,
) -> None:
    record.child_id = body.child_id
    record.activity_id = body.activity_id
    record.activity_date = body.activity_date
    record.completion_status = body.completion_status
    record.actual_duration_minutes = body.actual_duration_minutes
    record.child_response = body.child_response
    record.notes = body.notes
    if refresh_snapshot:
        record.activity_code_snapshot = activity.activity_code
        record.activity_name_snapshot = activity.name
        record.category_snapshot = activity.category
        record.objective_snapshot = activity.objective
        record.suggested_duration_snapshot = activity.suggested_duration_minutes


def duplicate_exists(db: Session, body: ActivityRecordInput, exclude_id: int | None = None) -> bool:
    query = select(ActivityRecord.id).where(
        ActivityRecord.child_id == body.child_id,
        ActivityRecord.activity_id == body.activity_id,
        ActivityRecord.activity_date == body.activity_date,
        ActivityRecord.completion_status == body.completion_status,
        ActivityRecord.actual_duration_minutes == body.actual_duration_minutes,
        ActivityRecord.child_response == body.child_response,
        ActivityRecord.notes == body.notes,
    )
    if exclude_id:
        query = query.where(ActivityRecord.id != exclude_id)
    return db.scalar(query) is not None


@router.get("/stats", response_model=ActivityStatsResponse)
def activity_stats(child_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)) -> dict:
    if child_id and not db.get(Child, child_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    child_filter = (ActivityRecord.child_id == child_id,) if child_id else ()
    today = date.today(); month_start = today.replace(day=1)
    total = db.scalar(select(func.count(ActivityRecord.id)).where(*child_filter)) or 0
    status_counts = dict(db.execute(select(ActivityRecord.completion_status, func.count(ActivityRecord.id)).where(*child_filter).group_by(ActivityRecord.completion_status)).all())
    category_counts = dict(db.execute(select(ActivityRecord.category_snapshot, func.count(ActivityRecord.id)).where(*child_filter).group_by(ActivityRecord.category_snapshot)).all())
    return {
        "total_records": total,
        "month_records": db.scalar(select(func.count(ActivityRecord.id)).where(*child_filter, ActivityRecord.activity_date >= month_start)) or 0,
        "completed_records": status_counts.get("COMPLETED", 0),
        "partial_records": status_counts.get("PARTIAL", 0),
        "not_completed_records": status_counts.get("NOT_COMPLETED", 0),
        "latest_activity_date": db.scalar(select(func.max(ActivityRecord.activity_date)).where(*child_filter)),
        "category_counts": category_counts,
    }


@router.get("", response_model=ActivityRecordListResponse)
def records_list(child_id:int|None=Query(default=None,ge=1),category:str|None=None,date_from:date|None=None,date_to:date|None=None,page:int=Query(default=1,ge=1),page_size:int=Query(default=10,ge=1,le=100),db:Session=Depends(get_db)) -> dict:
    validate_filters(db, child_id, category, date_from, date_to)
    records,total=query_records(db,child_id,category,date_from,date_to,page,page_size)
    return {"items":[record_to_dict(item,db) for item in records],"total":total,"page":page,"page_size":page_size}


@router.post("", response_model=ActivityRecordResponse, status_code=status.HTTP_201_CREATED)
def record_create(body: ActivityRecordInput, db: Session = Depends(get_db)) -> dict:
    _, activity = validate_relations(body, db)
    if duplicate_exists(db, body):
        raise HTTPException(status.HTTP_409_CONFLICT, "相同活动记录已存在，请勿重复提交")
    record = ActivityRecord(child_id=body.child_id,activity_id=body.activity_id,activity_date=body.activity_date,completion_status=body.completion_status,activity_code_snapshot="",activity_name_snapshot="",category_snapshot="",objective_snapshot="",suggested_duration_snapshot=activity.suggested_duration_minutes)
    apply_record(record, body, activity, refresh_snapshot=True)
    db.add(record); db.commit(); db.refresh(record)
    return record_to_dict(record,db)


@router.get("/{record_id}", response_model=ActivityRecordResponse)
def record_detail(record_id:int,db:Session=Depends(get_db)) -> dict:
    return record_to_dict(get_record_or_404(record_id,db),db)


@router.put("/{record_id}", response_model=ActivityRecordResponse)
def record_update(record_id:int,body:ActivityRecordInput,db:Session=Depends(get_db)) -> dict:
    record=get_record_or_404(record_id,db); _,activity=validate_relations(body,db,record)
    if duplicate_exists(db,body,record.id): raise HTTPException(status.HTTP_409_CONFLICT,"相同活动记录已存在，请勿重复提交")
    activity_changed = record.activity_id != body.activity_id
    apply_record(record, body, activity, refresh_snapshot=activity_changed)
    db.commit(); db.refresh(record)
    return record_to_dict(record,db)


@router.delete("/{record_id}")
def record_delete(record_id:int,db:Session=Depends(get_db)) -> dict:
    record=get_record_or_404(record_id,db); db.delete(record); db.commit(); return {"message":"活动记录已删除"}
