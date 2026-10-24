from sqlalchemy import Engine, text

MIGRATION_VERSION = "0002_create_children"


def run_migrations(target_engine: Engine) -> None:
    """以可重复、事务化方式升级已有数据库，不删除任何已有表或数据。"""
    from ..models.child import Child

    with target_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(100) PRIMARY KEY,
                    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        applied = connection.scalar(
            text("SELECT version FROM schema_migrations WHERE version = :version"),
            {"version": MIGRATION_VERSION},
        )
        if applied:
            return
        Child.__table__.create(bind=connection, checkfirst=True)
        connection.execute(
            text("INSERT INTO schema_migrations (version) VALUES (:version)"),
            {"version": MIGRATION_VERSION},
        )

