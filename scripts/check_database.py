import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text
from backend.app.core.config import settings
from backend.app.core.database import check_database, engine

check_database()
tables = set(inspect(engine).get_table_names())
missing = {"users", "auth_sessions", "children", "video_analyses", "observation_records", "schema_migrations"} - tables
if missing:
    raise SystemExit(f"缺少数据表：{', '.join(sorted(missing))}")
expected_migrations = {"0002_create_children", "0003_create_video_analyses", "0004_create_observation_records"}
with engine.connect() as connection:
    applied_migrations = {row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))}
missing_migrations = expected_migrations - applied_migrations
if missing_migrations:
    raise SystemExit(f"缺少迁移版本：{', '.join(sorted(missing_migrations))}")
print(f"数据库连接正常：{settings.database_path}")
print(f"基础数据表完整，迁移版本：{', '.join(sorted(applied_migrations))}")
