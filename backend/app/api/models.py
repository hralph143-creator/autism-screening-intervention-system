from fastapi import APIRouter, Depends

from ..core.security import get_current_user
from ..services.model_manager import model_status

router = APIRouter(prefix="/models", tags=["模型管理"], dependencies=[Depends(get_current_user)])


@router.get("/status")
def models_status() -> dict:
    return model_status(validate_load=True)
