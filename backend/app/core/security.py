import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from ..models.user import AuthSession, User
from .database import get_db

COOKIE_NAME = "autism_system_session"
SESSION_HOURS = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16); rounds = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds_text, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256": return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds_text))
        return hmac.compare_digest(actual, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User, response: Response) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(user_id=user.id, token_hash=token_hash(token), expires_at=now + timedelta(hours=SESSION_HOURS)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_HOURS * 3600, httponly=True, samesite="strict", secure=False, path="/")


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")


def get_current_user(token: str | None = Cookie(default=None, alias=COOKIE_NAME), db: Session = Depends(get_db)) -> User:
    if not token: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token), AuthSession.expires_at > now))
    if not session: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态无效或已过期")
    user = db.get(User, session.user_id)
    if not user: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态无效")
    return user

