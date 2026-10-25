import json

from sqlalchemy import Engine, text

MIGRATIONS = ("0002_create_children", "0003_create_video_analyses", "0004_create_observation_records", "0005_create_activities_and_records")


def run_migrations(target_engine: Engine) -> None:
    """以可重复、事务化方式升级已有数据库，不删除任何已有表或数据。"""
    from ..models.child import Child
    from ..models.video_analysis import VideoAnalysis
    from ..models.observation import ObservationRecord
    from ..models.activity import Activity, ActivityRecord
    from ..services.builtin_activities import BUILTIN_ACTIVITIES

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
            MIGRATIONS[3]: (Activity.__table__, ActivityRecord.__table__),
        }
        for version in MIGRATIONS:
            applied = connection.scalar(
                text("SELECT version FROM schema_migrations WHERE version = :version"), {"version": version}
            )
            if applied:
                continue
            migration_tables = tables[version] if isinstance(tables[version], tuple) else (tables[version],)
            for table in migration_tables:
                table.create(bind=connection, checkfirst=True)
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES (:version)"), {"version": version})
        existing_codes = set(connection.execute(text("SELECT activity_code FROM activities")).scalars())
        missing_activities = [
            {
                **item,
                "materials": json.dumps(item["materials"], ensure_ascii=False),
                "steps": json.dumps(item["steps"], ensure_ascii=False),
                "is_active": True,
                "is_builtin": True,
            }
            for item in BUILTIN_ACTIVITIES
            if item["activity_code"] not in existing_codes
        ]
        if missing_activities:
            connection.execute(Activity.__table__.insert(), missing_activities)
