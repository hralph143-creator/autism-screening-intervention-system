from datetime import date
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.child import Child
from ..models.observation import ObservationRecord
from ..models.video_analysis import VideoAnalysis
from ..schemas.observation import ObservationInput, ObservationListResponse, ObservationResponse
from ..services.observation_definition import form_definition
from ..services.observations import observation_to_dict, query_observations

router = APIRouter(prefix="/observations", tags=["行为观察"], dependencies=[Depends(get_current_user)])


def get_observation_or_404(observation_id: int, db: Session) -> ObservationRecord:
    record = db.get(ObservationRecord, observation_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "行为观察记录不存在")
    return record


def validate_relations(body: ObservationInput, db: Session) -> None:
    if not db.get(Child, body.child_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    if body.video_analysis_id is None:
        return
    video = db.get(VideoAnalysis, body.video_analysis_id)
    if not video:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "关联的视频分析记录不存在")
    if video.child_id != body.child_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "只能关联同一儿童的视频分析记录")


def list_records(
    db: Session,
    child_id: int | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "开始日期不能晚于结束日期")
    if child_id and not db.get(Child, child_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    records, total = query_observations(db, child_id, date_from, date_to, page, page_size)
    return {"items": [observation_to_dict(item, db) for item in records], "total": total, "page": page, "page_size": page_size}


@router.get("/form-definition")
def observation_form_definition() -> dict:
    return form_definition()


@router.get("", response_model=ObservationListResponse)
def observations_list(
    child_id: int | None = Query(default=None, ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return list_records(db, child_id, date_from, date_to, page, page_size)


@router.post("", response_model=ObservationResponse, status_code=status.HTTP_201_CREATED)
def observation_create(body: ObservationInput, db: Session = Depends(get_db)) -> dict:
    validate_relations(body, db)
    record = ObservationRecord(
        child_id=body.child_id,
        video_analysis_id=body.video_analysis_id,
        observation_date=body.observation_date,
        observation_scene=body.observation_scene,
        observer_role=body.observer_role,
        observation_data=json.dumps(body.observation_data, ensure_ascii=False, sort_keys=True),
        summary_notes=body.summary_notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return observation_to_dict(record, db)


@router.get("/{observation_id}", response_model=ObservationResponse)
def observation_detail(observation_id: int, db: Session = Depends(get_db)) -> dict:
    return observation_to_dict(get_observation_or_404(observation_id, db), db)


@router.put("/{observation_id}", response_model=ObservationResponse)
def observation_update(observation_id: int, body: ObservationInput, db: Session = Depends(get_db)) -> dict:
    record = get_observation_or_404(observation_id, db)
    validate_relations(body, db)
    record.child_id = body.child_id
    record.video_analysis_id = body.video_analysis_id
    record.observation_date = body.observation_date
    record.observation_scene = body.observation_scene
    record.observer_role = body.observer_role
    record.observation_data = json.dumps(body.observation_data, ensure_ascii=False, sort_keys=True)
    record.summary_notes = body.summary_notes
    db.commit()
    db.refresh(record)
    return observation_to_dict(record, db)


@router.delete("/{observation_id}")
def observation_delete(observation_id: int, db: Session = Depends(get_db)) -> dict:
    record = get_observation_or_404(observation_id, db)
    db.delete(record)
    db.commit()
    return {"message": "行为观察记录已删除"}
