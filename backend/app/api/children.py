from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.child import Child
from ..models.video_analysis import VideoAnalysis
from ..schemas.child import ChildCreate, ChildListResponse, ChildResponse, ChildUpdate
from ..schemas.observation import ObservationListResponse
from ..services.children import child_to_dict, create_child, delete_child, list_children, update_child
from ..services.observations import observation_to_dict, query_observations
from ..services.video_storage import remove_analysis_files

router = APIRouter(prefix="/children", tags=["儿童档案"], dependencies=[Depends(get_current_user)])


def get_child_or_404(child_id: int, db: Session) -> Child:
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    return child


@router.get("", response_model=ChildListResponse)
def children_list(
    q: str = Query(default="", max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_order: Literal["desc", "asc"] = "desc",
    db: Session = Depends(get_db),
) -> dict:
    items, total = list_children(db, q.strip(), page, page_size, sort_order)
    return {"items": [child_to_dict(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
def children_create(body: ChildCreate, db: Session = Depends(get_db)) -> dict:
    return child_to_dict(create_child(db, body))


@router.get("/{child_id}", response_model=ChildResponse)
def children_detail(child_id: int, db: Session = Depends(get_db)) -> dict:
    return child_to_dict(get_child_or_404(child_id, db))


@router.get("/{child_id}/observations", response_model=ObservationListResponse)
def child_observations(
    child_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    get_child_or_404(child_id, db)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "开始日期不能晚于结束日期")
    records, total = query_observations(db, child_id, date_from, date_to, page, page_size)
    return {"items": [observation_to_dict(item, db) for item in records], "total": total, "page": page, "page_size": page_size}


@router.put("/{child_id}", response_model=ChildResponse)
def children_update(child_id: int, body: ChildUpdate, db: Session = Depends(get_db)) -> dict:
    child = get_child_or_404(child_id, db)
    return child_to_dict(update_child(db, child, body))


@router.delete("/{child_id}")
def children_delete(child_id: int, db: Session = Depends(get_db)) -> dict:
    child = get_child_or_404(child_id, db)
    analyses = db.scalars(select(VideoAnalysis).where(VideoAnalysis.child_id == child_id)).all()
    if any(item.status in ("PENDING", "RUNNING") for item in analyses):
        raise HTTPException(status.HTTP_409_CONFLICT, "该档案存在等待或运行中的视频任务，请等待任务结束后再删除")
    for item in analyses:
        remove_analysis_files(item)
    delete_child(db, child)
    return {"message": "儿童档案已删除"}
