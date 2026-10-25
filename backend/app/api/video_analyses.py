from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.child import Child
from ..models.video_analysis import VideoAnalysis
from ..schemas.video_analysis import VideoAnalysisListResponse, VideoAnalysisResponse, VideoAnalysisResultResponse
from ..services.analysis_queue import analysis_queue
from ..services.model_manager import model_status
from ..services.video_files import VideoValidationError, inspect_video
from ..services.video_storage import remove_analysis_files

router = APIRouter(prefix="/video-analyses", tags=["视频分析"], dependencies=[Depends(get_current_user)])
ACTIVE_STATUSES = ("PENDING", "RUNNING")


def get_record_or_404(analysis_id: int, db: Session) -> VideoAnalysis:
    record = db.get(VideoAnalysis, analysis_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "视频分析记录不存在")
    return record


def serialize(record: VideoAnalysis, db: Session) -> dict:
    child = db.get(Child, record.child_id)
    sampled_frames = None
    if record.status == "COMPLETED" and record.result_json:
        try:
            sampled_frames = int(json.loads(record.result_json).get("summary", {}).get("sampled_frames"))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return {
        "id": record.id,
        "child_id": record.child_id,
        "child_code": child.child_code if child else "已删除",
        "child_nickname": child.nickname if child else "已删除档案",
        "original_filename": record.original_filename,
        "file_size": record.file_size,
        "duration_seconds": record.duration_seconds,
        "width": record.width,
        "height": record.height,
        "source_fps": record.source_fps,
        "status": record.status,
        "progress": record.progress,
        "error_message": record.error_message,
        "retry_count": record.retry_count,
        "sampled_frames": sampled_frames,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
    }


@router.get("", response_model=VideoAnalysisListResponse)
def analyses_list(
    child_id: int | None = Query(default=None, ge=1),
    task_status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "INTERRUPTED"] | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if child_id:
        filters.append(VideoAnalysis.child_id == child_id)
    if task_status:
        filters.append(VideoAnalysis.status == task_status)
    total = db.scalar(select(func.count(VideoAnalysis.id)).where(*filters)) or 0
    records = db.scalars(
        select(VideoAnalysis).where(*filters).order_by(VideoAnalysis.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [serialize(item, db) for item in records], "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=VideoAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def analysis_create(
    child_id: int = Form(...),
    consent_confirmed: bool = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    if not consent_confirmed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "必须确认已获得监护人授权并了解隐私用途")
    if not db.get(Child, child_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    original_name = Path(file.filename or "").name
    if not original_name or Path(original_name).suffix.lower() != ".mp4":
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "仅支持 MP4 视频")
    readiness = model_status(validate_load=True)
    if not readiness["ready"]:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, readiness["error"] or "分析模型不可用")
    stored_name = f"{uuid.uuid4().hex}.mp4"
    destination = settings.upload_dir / stored_name
    digest = hashlib.sha256()
    total = 0
    committed = False
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_video_bytes:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "视频大小不能超过 100 MB")
                digest.update(chunk)
                output.write(chunk)
        if total == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "视频文件为空")
        try:
            metadata = inspect_video(destination)
        except VideoValidationError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        sha256 = digest.hexdigest()
        duplicate = db.scalar(
            select(VideoAnalysis).where(
                VideoAnalysis.child_id == child_id,
                VideoAnalysis.file_sha256 == sha256,
                VideoAnalysis.status.in_(("PENDING", "RUNNING", "COMPLETED")),
            )
        )
        if duplicate:
            raise HTTPException(status.HTTP_409_CONFLICT, f"该视频已有分析记录（任务 #{duplicate.id}）")
        record = VideoAnalysis(
            child_id=child_id,
            original_filename=original_name[:255],
            stored_filename=stored_name,
            file_path=str(destination.resolve()),
            file_sha256=sha256,
            file_size=total,
            duration_seconds=float(metadata["duration_seconds"]),
            width=int(metadata["width"]),
            height=int(metadata["height"]),
            source_fps=float(metadata["source_fps"]),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        committed = True
    except Exception:
        if destination.exists() and not committed:
            destination.unlink()
        raise
    finally:
        await file.close()
    analysis_queue.enqueue(record.id)
    return serialize(record, db)


@router.get("/{analysis_id}", response_model=VideoAnalysisResponse)
def analysis_detail(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    return serialize(get_record_or_404(analysis_id, db), db)


@router.get("/{analysis_id}/status", response_model=VideoAnalysisResponse)
def analysis_status(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    return serialize(get_record_or_404(analysis_id, db), db)


@router.get("/{analysis_id}/result", response_model=VideoAnalysisResultResponse)
def analysis_result(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    record = get_record_or_404(analysis_id, db)
    if record.status != "COMPLETED" or not record.result_json:
        raise HTTPException(status.HTTP_409_CONFLICT, "分析结果尚未生成")
    return {"analysis": serialize(record, db), "result": json.loads(record.result_json)}


@router.get("/{analysis_id}/frames/{filename}")
def analysis_frame(analysis_id: int, filename: str, db: Session = Depends(get_db)) -> FileResponse:
    record = get_record_or_404(analysis_id, db)
    if record.status != "COMPLETED" or not record.result_json or not record.result_dir:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "结果帧不存在")
    result = json.loads(record.result_json)
    allowed = {item["filename"] for item in result.get("preview_frames", [])}
    if filename not in allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "结果帧不存在")
    target = (Path(record.result_dir) / filename).resolve()
    root = Path(record.result_dir).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "结果帧不存在")
    return FileResponse(target, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.post("/{analysis_id}/retry", response_model=VideoAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
def analysis_retry(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    record = get_record_or_404(analysis_id, db)
    if record.status in ACTIVE_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "任务正在等待或运行，不能重复提交")
    if not Path(record.file_path).is_file():
        raise HTTPException(status.HTTP_409_CONFLICT, "原视频文件已丢失，无法重试")
    readiness = model_status(validate_load=True)
    if not readiness["ready"]:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, readiness["error"] or "分析模型不可用")
    if record.result_dir:
        result_target = Path(record.result_dir).resolve()
        result_root = settings.analysis_result_dir.resolve()
        if result_target != result_root and result_target.is_relative_to(result_root) and result_target.exists():
            shutil.rmtree(result_target)
    record.status = "PENDING"
    record.progress = 0
    record.error_message = None
    record.result_json = None
    record.result_dir = None
    record.retry_count += 1
    record.started_at = None
    record.completed_at = None
    record.updated_at = datetime.utcnow()
    db.commit()
    analysis_queue.enqueue(record.id)
    return serialize(record, db)


@router.delete("/{analysis_id}")
def analysis_delete(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    record = get_record_or_404(analysis_id, db)
    if record.status in ACTIVE_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "等待或运行中的任务不能删除")
    remove_analysis_files(record)
    db.delete(record)
    db.commit()
    return {"message": "视频、分析结果和记录已删除"}
