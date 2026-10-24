from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import COOKIE_NAME, clear_session_cookie, create_session, get_current_user, hash_password, token_hash, verify_password
from ..models.user import AuthSession, User
from ..schemas.auth import InitializeRequest, LoginRequest

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/status")
def initialization_status(db: Session = Depends(get_db)) -> dict:
    return {"initialized": bool(db.scalar(select(func.count(User.id))))}


@router.post("/initialize", status_code=status.HTTP_201_CREATED)
def initialize_admin(body: InitializeRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(func.count(User.id))): raise HTTPException(status.HTTP_409_CONFLICT, "管理员已初始化")
    user = User(singleton_slot=1, username=body.username, password_hash=hash_password(body.password)); db.add(user)
    try:
        db.commit(); db.refresh(user)
    except IntegrityError:
        db.rollback(); raise HTTPException(status.HTTP_409_CONFLICT, "管理员已初始化")
    create_session(db, user, response)
    return {"id": user.id, "username": user.username}


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.username == body.username.strip()))
    if not user or not verify_password(body.password, user.password_hash): raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    create_session(db, user, response)
    return {"id": user.id, "username": user.username}


@router.get("/me")
def current_admin(user: User = Depends(get_current_user)) -> dict:
    return {"id": user.id, "username": user.username}


@router.post("/logout")
def logout(response: Response, token: str | None = Cookie(default=None, alias=COOKIE_NAME), db: Session = Depends(get_db)) -> dict:
    if token:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        if session: db.delete(session); db.commit()
    clear_session_cookie(response)
    return {"message": "已安全退出"}

