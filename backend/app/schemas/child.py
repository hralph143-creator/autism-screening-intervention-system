import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BIRTH_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class ChildBase(BaseModel):
    nickname: str = Field(min_length=1, max_length=50)
    birth_month: str | None = None
    gender: Literal["男", "女", "未说明"] | None = None
    development_notes: str | None = Field(default=None, max_length=4000)
    guardian_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("档案昵称不能为空")
        return value

    @field_validator("birth_month")
    @classmethod
    def validate_birth_month(cls, value: str | None) -> str | None:
        value = clean_optional_text(value)
        if value is None:
            return None
        if not BIRTH_MONTH_PATTERN.fullmatch(value):
            raise ValueError("出生年月格式应为 YYYY-MM")
        parsed = datetime.strptime(value, "%Y-%m").date()
        current_month = date.today().replace(day=1)
        if parsed.year < 1900:
            raise ValueError("出生年月不能早于 1900-01")
        if parsed > current_month:
            raise ValueError("出生年月不能晚于当前月份")
        return value

    @field_validator("development_notes", "guardian_notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return clean_optional_text(value)


class ChildCreate(ChildBase):
    pass


class ChildUpdate(ChildBase):
    pass


class ChildResponse(ChildBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    child_code: str
    age_text: str
    created_at: datetime
    updated_at: datetime


class ChildListResponse(BaseModel):
    items: list[ChildResponse]
    total: int
    page: int
    page_size: int


class DashboardStatsResponse(BaseModel):
    total_children: int
    added_this_month: int
    recent_children: list[ChildResponse]

