import uuid
from datetime import date, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.child import Child
from ..schemas.child import ChildCreate, ChildUpdate


def age_text(birth_month: str | None) -> str:
    if not birth_month:
        return "未填写"
    year, month = (int(part) for part in birth_month.split("-"))
    today = date.today()
    months = (today.year - year) * 12 + today.month - month
    years, remaining = divmod(max(months, 0), 12)
    if years == 0:
        return f"{remaining}个月"
    return f"{years}岁" if remaining == 0 else f"{years}岁{remaining}个月"


def child_to_dict(child: Child) -> dict:
    return {
        "id": child.id,
        "child_code": child.child_code,
        "nickname": child.nickname,
        "birth_month": child.birth_month,
        "age_text": age_text(child.birth_month),
        "gender": child.gender,
        "development_notes": child.development_notes,
        "guardian_notes": child.guardian_notes,
        "created_at": child.created_at,
        "updated_at": child.updated_at,
    }


def generate_child_code() -> str:
    return f"CH-{date.today():%Y%m}-{uuid.uuid4().hex[:8].upper()}"


def create_child(db: Session, body: ChildCreate) -> Child:
    for _attempt in range(3):
        child = Child(child_code=generate_child_code(), **body.model_dump())
        db.add(child)
        try:
            db.commit()
            db.refresh(child)
            return child
        except IntegrityError:
            db.rollback()
    raise RuntimeError("无法生成唯一儿童编号，请重试")


def list_children(db: Session, query: str, page: int, page_size: int, sort_order: str) -> tuple[list[Child], int]:
    filters = []
    if query:
        pattern = f"%{query}%"
        filters.append(or_(Child.child_code.ilike(pattern), Child.nickname.ilike(pattern)))
    count_stmt = select(func.count(Child.id))
    item_stmt: Select = select(Child)
    if filters:
        count_stmt = count_stmt.where(*filters)
        item_stmt = item_stmt.where(*filters)
    order = Child.created_at.asc() if sort_order == "asc" else Child.created_at.desc()
    item_stmt = item_stmt.order_by(order, Child.id.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(item_stmt).all()), int(db.scalar(count_stmt) or 0)


def update_child(db: Session, child: Child, body: ChildUpdate) -> Child:
    for key, value in body.model_dump().items():
        setattr(child, key, value)
    child.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(child)
    return child


def delete_child(db: Session, child: Child) -> None:
    """后续有关联业务表时，在此处统一扩展文件与关联记录清理。"""
    db.delete(child)
    db.commit()

