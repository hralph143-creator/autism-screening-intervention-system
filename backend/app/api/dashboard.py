from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.child import Child
from ..schemas.child import DashboardStatsResponse
from ..services.children import child_to_dict

router = APIRouter(prefix="/dashboard", tags=["首页"], dependencies=[Depends(get_current_user)])


@router.get("/stats", response_model=DashboardStatsResponse)
def dashboard_stats(db: Session = Depends(get_db)) -> dict:
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    total = int(db.scalar(select(func.count(Child.id))) or 0)
    added = int(db.scalar(select(func.count(Child.id)).where(Child.created_at >= month_start)) or 0)
    recent = db.scalars(select(Child).order_by(Child.created_at.desc(), Child.id.desc()).limit(5)).all()
    return {"total_children": total, "added_this_month": added, "recent_children": [child_to_dict(child) for child in recent]}

