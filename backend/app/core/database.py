from collections.abc import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from .config import ensure_runtime_dirs, settings


class Base(DeclarativeBase):
    pass


ensure_runtime_dirs()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    from ..models.user import AuthSession, User
    from ..migrations import run_migrations
    Base.metadata.create_all(bind=engine, tables=[User.__table__, AuthSession.__table__])
    run_migrations(engine)
    check_database()


def check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        raise RuntimeError(f"SQLite 数据库无法访问：{settings.database_path}。原因：{exc}") from exc


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
