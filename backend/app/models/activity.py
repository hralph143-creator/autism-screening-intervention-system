from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    age_min_months: Mapped[int] = mapped_column(Integer)
    age_max_months: Mapped[int] = mapped_column(Integer)
    objective: Mapped[str] = mapped_column(Text)
    materials: Mapped[str] = mapped_column(Text)
    steps: Mapped[str] = mapped_column(Text)
    suggested_duration_minutes: Mapped[int] = mapped_column(Integer)
    precautions: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityRecord(Base):
    __tablename__ = "activity_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="RESTRICT"), index=True)
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    completion_status: Mapped[str] = mapped_column(String(20), index=True)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    child_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    activity_code_snapshot: Mapped[str] = mapped_column(String(32))
    activity_name_snapshot: Mapped[str] = mapped_column(String(100))
    category_snapshot: Mapped[str] = mapped_column(String(40), index=True)
    objective_snapshot: Mapped[str] = mapped_column(Text)
    suggested_duration_snapshot: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
