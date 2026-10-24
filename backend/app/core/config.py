import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    app_name: str = "基于深度学习的自闭症筛查与干预系统"
    environment: str = os.getenv("APP_ENV", "development")
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8001"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    data_dir: Path = Path(os.getenv("APP_DATA_DIR", PROJECT_ROOT / "data"))
    frontend_origins: tuple[str, ...] = tuple(
        value.strip()
        for value in os.getenv("FRONTEND_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
        if value.strip()
    )

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"


settings = Settings()


def ensure_runtime_dirs() -> None:
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"无法创建数据目录：{settings.data_dir}。原因：{exc}") from exc

