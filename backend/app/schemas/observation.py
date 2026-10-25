from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..services.observation_definition import ITEMS, OBSERVATION_SCENES, OBSERVER_ROLES

ObservationValue = Literal["OFTEN", "SOMETIMES", "NOT_SEEN_THIS_TIME", "UNABLE_TO_JUDGE", "NOT_OBSERVED"]


class ObservationInput(BaseModel):
    child_id: int = Field(gt=0)
    video_analysis_id: int | None = Field(default=None, gt=0)
    observation_date: date
    observation_scene: str = Field(max_length=30)
    observer_role: str = Field(max_length=30)
    observation_data: dict[str, ObservationValue]
    summary_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("observation_date")
    @classmethod
    def valid_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("观察日期不能晚于今天")
        if value < date(2000, 1, 1):
            raise ValueError("观察日期不能早于 2000-01-01")
        return value

    @field_validator("observation_scene")
    @classmethod
    def valid_scene(cls, value: str) -> str:
        value = value.strip()
        if value not in OBSERVATION_SCENES:
            raise ValueError("观察场景不在允许范围内")
        return value

    @field_validator("observer_role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        value = value.strip()
        if value not in OBSERVER_ROLES:
            raise ValueError("观察者身份不在允许范围内")
        return value

    @field_validator("observation_data")
    @classmethod
    def valid_observation_data(cls, value: dict[str, ObservationValue]) -> dict[str, ObservationValue]:
        if not value:
            raise ValueError("请至少填写一个观察项目")
        unknown = set(value) - set(ITEMS)
        if unknown:
            raise ValueError(f"包含未知观察项目：{', '.join(sorted(unknown))}")
        return value

    @field_validator("summary_notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LinkedVideoResponse(BaseModel):
    id: int
    original_filename: str
    status: str
    created_at: datetime
    sampled_frames: int | None


class ObservationResponse(BaseModel):
    id: int
    child_id: int
    child_code: str
    child_nickname: str
    video_analysis_id: int | None
    linked_video: LinkedVideoResponse | None
    observation_date: date
    observation_scene: str
    observer_role: str
    observation_data: dict[str, ObservationValue]
    observation_items: list[dict]
    summary_notes: str | None
    auxiliary_summary: str
    data_completeness: dict
    disclaimer: str
    created_at: datetime
    updated_at: datetime


class ObservationListResponse(BaseModel):
    items: list[ObservationResponse]
    total: int
    page: int
    page_size: int
