import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import settings
from backend.app.core.database import initialize_database

initialize_database()
print(f"SQLite 数据库初始化完成：{settings.database_path}")
print("管理员账号将在首次打开系统时由用户创建。")
