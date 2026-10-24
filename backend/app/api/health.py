import logging

from fastapi import APIRouter, HTTPException, status
from ..core.database import check_database

router = APIRouter(tags=["系统"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check() -> dict:
    try: check_database()
    except RuntimeError as exc:
        logger.error("数据库健康检查失败：%s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "数据库连接异常")
    return {"status": "ok", "database": "connected"}
