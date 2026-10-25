from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.child import Child
from ..services.history import RECORD_TYPES, build_report, child_overview, timeline_query, validate_date_range

router = APIRouter(prefix="/children", tags=["综合历史与报告"], dependencies=[Depends(get_current_user)])


def child_or_404(child_id: int, db: Session) -> Child:
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    return child


def validate_range(start_date: date | None, end_date: date | None) -> None:
    try:
        validate_date_range(start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/{child_id}/overview")
def overview(child_id: int, db: Session = Depends(get_db)) -> dict:
    return child_overview(db, child_or_404(child_id, db))


@router.get("/{child_id}/timeline")
def timeline(
    child_id: int,
    record_type: Literal["VIDEO", "OBSERVATION", "ACTIVITY"] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    sort_order: Literal["desc", "asc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    child_or_404(child_id, db); validate_range(start_date, end_date)
    return timeline_query(db, child_id, record_type, start_date, end_date, page, page_size, sort_order)


@router.get("/{child_id}/report")
def report(
    child_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    record_types: str = Query(default="VIDEO,OBSERVATION,ACTIVITY", min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> dict:
    child = child_or_404(child_id, db); validate_range(start_date, end_date)
    selected = tuple(dict.fromkeys(item.strip().upper() for item in record_types.split(",") if item.strip()))
    if not selected or any(item not in RECORD_TYPES for item in selected):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "报告记录类型不正确")
    return build_report(db, child, start_date, end_date, selected)
