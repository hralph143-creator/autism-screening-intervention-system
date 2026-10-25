import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.activity import Activity
from ..models.child import Child
from ..schemas.activity import ActivityCreate, ActivityListResponse, ActivityResponse, ActivityStatusUpdate, ActivityUpdate
from ..services.activities import activity_to_dict, age_in_months, apply_activity_fields
from ..services.builtin_activities import ACTIVITY_CATEGORIES, ACTIVITY_DISCLAIMER

router = APIRouter(prefix="/activities", tags=["家庭互动活动"], dependencies=[Depends(get_current_user)])


def get_activity_or_404(activity_id: int, db: Session) -> Activity:
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "活动不存在")
    return activity


@router.get("", response_model=ActivityListResponse)
def activities_list(
    q: str = Query(default="", max_length=100),
    category: str | None = None,
    child_id: int | None = Query(default=None, ge=1),
    active_only: bool = True,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    if category and category not in ACTIVITY_CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "活动分类不在允许范围内")
    age_filter = None
    filters = []
    if q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(Activity.name.like(pattern), Activity.activity_code.like(pattern)))
    if category:
        filters.append(Activity.category == category)
    if active_only:
        filters.append(Activity.is_active.is_(True))
    if child_id:
        child = db.get(Child, child_id)
        if not child:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
        if child.birth_month:
            months = age_in_months(child.birth_month)
            filters.extend((Activity.age_min_months <= months, Activity.age_max_months >= months))
            age_filter = {"child_id": child_id, "applied": True, "age_months": months, "message": "已按儿童月龄进行参考筛选"}
        else:
            age_filter = {"child_id": child_id, "applied": False, "age_months": None, "message": "该档案未填写出生年月，未应用年龄筛选"}
    total = db.scalar(select(func.count(Activity.id)).where(*filters)) or 0
    activities = db.scalars(select(Activity).where(*filters).order_by(Activity.category, Activity.activity_code).offset((page-1)*page_size).limit(page_size)).all()
    return {"items":[activity_to_dict(item) for item in activities],"total":total,"page":page,"page_size":page_size,"categories":ACTIVITY_CATEGORIES,"age_filter":age_filter,"disclaimer":ACTIVITY_DISCLAIMER}


@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
def activity_create(body: ActivityCreate, db: Session = Depends(get_db)) -> dict:
    code = body.activity_code or f"ACT-CUS-{uuid.uuid4().hex[:8].upper()}"
    if db.scalar(select(Activity).where(Activity.activity_code == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "活动编号已存在")
    activity = Activity(activity_code=code, is_active=True, is_builtin=False, name="", category="", age_min_months=0, age_max_months=0, objective="", materials="[]", steps="[]", suggested_duration_minutes=1, precautions="")
    apply_activity_fields(activity, body)
    db.add(activity)
    try:
        db.commit(); db.refresh(activity)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status.HTTP_409_CONFLICT, "活动编号已存在") from exc
    return activity_to_dict(activity)


@router.get("/{activity_id}", response_model=ActivityResponse)
def activity_detail(activity_id: int, db: Session = Depends(get_db)) -> dict:
    return activity_to_dict(get_activity_or_404(activity_id, db))


@router.put("/{activity_id}", response_model=ActivityResponse)
def activity_update(activity_id: int, body: ActivityUpdate, db: Session = Depends(get_db)) -> dict:
    activity = get_activity_or_404(activity_id, db)
    apply_activity_fields(activity, body)
    db.commit(); db.refresh(activity)
    return activity_to_dict(activity)


@router.patch("/{activity_id}/status", response_model=ActivityResponse)
def activity_status(activity_id: int, body: ActivityStatusUpdate, db: Session = Depends(get_db)) -> dict:
    activity = get_activity_or_404(activity_id, db)
    activity.is_active = body.is_active
    db.commit(); db.refresh(activity)
    return activity_to_dict(activity)
