from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.child import Child
from ..schemas.child import ChildCreate, ChildListResponse, ChildResponse, ChildUpdate
from ..services.children import child_to_dict, create_child, delete_child, list_children, update_child

router = APIRouter(prefix="/children", tags=["儿童档案"], dependencies=[Depends(get_current_user)])


def get_child_or_404(child_id: int, db: Session) -> Child:
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "儿童档案不存在")
    return child


@router.get("", response_model=ChildListResponse)
def children_list(
    q: str = Query(default="", max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_order: Literal["desc", "asc"] = "desc",
    db: Session = Depends(get_db),
) -> dict:
    items, total = list_children(db, q.strip(), page, page_size, sort_order)
    return {"items": [child_to_dict(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
def children_create(body: ChildCreate, db: Session = Depends(get_db)) -> dict:
    return child_to_dict(create_child(db, body))


@router.get("/{child_id}", response_model=ChildResponse)
def children_detail(child_id: int, db: Session = Depends(get_db)) -> dict:
    return child_to_dict(get_child_or_404(child_id, db))


@router.put("/{child_id}", response_model=ChildResponse)
def children_update(child_id: int, body: ChildUpdate, db: Session = Depends(get_db)) -> dict:
    child = get_child_or_404(child_id, db)
    return child_to_dict(update_child(db, child, body))


@router.delete("/{child_id}")
def children_delete(child_id: int, db: Session = Depends(get_db)) -> dict:
    child = get_child_or_404(child_id, db)
    delete_child(db, child)
    return {"message": "儿童档案已删除"}
