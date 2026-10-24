import platform
from fastapi import APIRouter, Depends
from ..core.config import settings
from ..core.database import check_database
from ..core.security import get_current_user
from ..models.user import User

router = APIRouter(prefix="/system", tags=["系统"])


@router.get("/info")
def system_info(user: User = Depends(get_current_user)) -> dict:
    return {"name": settings.app_name, "service_status": "running", "database_status": "connected" if check_database() else "unavailable", "backend": {"framework": "FastAPI", "python": platform.python_version()}, "environment": settings.environment, "administrator": user.username}

