from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class ObservationRecord(Base):
    __tablename__ = "observation_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), index=True)
    video_analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey("video_analyses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    observation_date: Mapped[date] = mapped_column(Date, index=True)
    observation_scene: Mapped[str] = mapped_column(String(30))
    observer_role: Mapped[str] = mapped_column(String(30))
    observation_data: Mapped[str] = mapped_column(Text)
    summary_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
