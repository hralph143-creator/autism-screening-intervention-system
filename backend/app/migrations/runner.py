from sqlalchemy import Engine, text

MIGRATIONS = ("0002_create_children", "0003_create_video_analyses", "0004_create_observation_records")


def run_migrations(target_engine: Engine) -> None:
    """以可重复、事务化方式升级已有数据库，不删除任何已有表或数据。"""
    from ..models.child import Child
    from ..models.video_analysis import VideoAnalysis
    from ..models.observation import ObservationRecord

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
        tables = {
            MIGRATIONS[0]: Child.__table__,
            MIGRATIONS[1]: VideoAnalysis.__table__,
            MIGRATIONS[2]: ObservationRecord.__table__,
        }
        for version in MIGRATIONS:
            applied = connection.scalar(
                text("SELECT version FROM schema_migrations WHERE version = :version"), {"version": version}
            )
            if applied:
                continue
            tables[version].create(bind=connection, checkfirst=True)
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES (:version)"), {"version": version})
