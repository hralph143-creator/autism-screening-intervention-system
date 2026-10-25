import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..services.builtin_activities import ACTIVITY_CATEGORIES

CompletionStatus = Literal["COMPLETED", "PARTIAL", "NOT_COMPLETED"]


class ActivityFields(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(max_length=40)
    age_min_months: int = Field(ge=0, le=216)
    age_max_months: int = Field(ge=0, le=216)
    objective: str = Field(min_length=1, max_length=2000)
    materials: list[str] = Field(min_length=1, max_length=20)
    steps: list[str] = Field(min_length=1, max_length=15)
    suggested_duration_minutes: int = Field(ge=1, le=180)
    precautions: str = Field(min_length=1, max_length=2000)

    @field_validator("name", "objective", "precautions")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("内容不能为空")
        return cleaned

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str) -> str:
        if value not in ACTIVITY_CATEGORIES:
            raise ValueError("活动分类不在允许范围内")
        return value

    @field_validator("materials", "steps")
    @classmethod
    def clean_lines(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("至少需要填写一项")
        if any(len(item) > 500 for item in cleaned):
            raise ValueError("单项内容不能超过500字")
        return cleaned

    @model_validator(mode="after")
    def valid_age_range(self):
        if self.age_min_months > self.age_max_months:
            raise ValueError("最小适用月龄不能大于最大适用月龄")
        return self


class ActivityCreate(ActivityFields):
    activity_code: str | None = Field(default=None, max_length=32)

    @field_validator("activity_code")
    @classmethod
    def valid_code(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9-]{3,32}", value):
            raise ValueError("活动编号只能包含大写字母、数字和连字符")
        return value


class ActivityUpdate(ActivityFields):
    pass


class ActivityStatusUpdate(BaseModel):
    is_active: bool


class ActivityResponse(ActivityFields):
    id: int
    activity_code: str
    is_active: bool
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class ActivityListResponse(BaseModel):
    items: list[ActivityResponse]
    total: int
    page: int
    page_size: int
    categories: list[str]
    age_filter: dict | None
    disclaimer: str


class ActivityRecordInput(BaseModel):
    child_id: int = Field(gt=0)
    activity_id: int = Field(gt=0)
    activity_date: date
    completion_status: CompletionStatus
    actual_duration_minutes: int | None = Field(default=None, ge=0, le=480)
    child_response: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("activity_date")
    @classmethod
    def valid_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("活动日期不能晚于今天")
        if value < date(2000, 1, 1):
            raise ValueError("活动日期不能早于2000-01-01")
        return value

    @field_validator("child_response", "notes")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ActivityRecordResponse(BaseModel):
    id: int
    child_id: int
    child_code: str
    child_nickname: str
    activity_id: int
    activity_code: str
    activity_name: str
    activity_category: str
    activity_objective: str
    suggested_duration_minutes: int
    activity_date: date
    completion_status: CompletionStatus
    completion_label: str
    actual_duration_minutes: int | None
    child_response: str | None
    notes: str | None
    activity_is_active: bool
    created_at: datetime
    updated_at: datetime
    disclaimer: str


class ActivityRecordListResponse(BaseModel):
    items: list[ActivityRecordResponse]
    total: int
    page: int
    page_size: int


class ActivityStatsResponse(BaseModel):
    total_records: int
    month_records: int
    completed_records: int
    partial_records: int
    not_completed_records: int
    latest_activity_date: date | None
    category_counts: dict[str, int]
