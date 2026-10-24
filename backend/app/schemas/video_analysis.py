from datetime import datetime
from typing import Any

from pydantic import BaseModel


class VideoAnalysisResponse(BaseModel):
    id: int
    child_id: int
    child_code: str
    child_nickname: str
    original_filename: str
    file_size: int
    duration_seconds: float
    width: int
    height: int
    source_fps: float
    status: str
    progress: int
    error_message: str | None
    retry_count: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class VideoAnalysisListResponse(BaseModel):
    items: list[VideoAnalysisResponse]
    total: int
    page: int
    page_size: int


class VideoAnalysisResultResponse(BaseModel):
    analysis: VideoAnalysisResponse
    result: dict[str, Any]
