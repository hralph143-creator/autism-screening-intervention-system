from sqlalchemy import inspect
from backend.app.core.config import settings
from backend.app.core.database import check_database, engine

check_database()
tables = set(inspect(engine).get_table_names())
missing = {"users", "auth_sessions", "children", "schema_migrations"} - tables
if missing:
    raise SystemExit(f"缺少数据表：{', '.join(sorted(missing))}")
print(f"数据库连接正常：{settings.database_path}")
print("基础数据表完整。")
