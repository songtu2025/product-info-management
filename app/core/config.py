import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "Amazon 运营数据管理后台"
    service_name: str = "amazon-ops-admin"
    database_url: str | None = None


def get_settings() -> Settings:
    env_file = os.getenv("APP_ENV_FILE", ".env")
    load_dotenv(Path(env_file), override=False)
    return Settings(database_url=os.getenv("DATABASE_URL"))
