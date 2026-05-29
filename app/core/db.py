from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.engine import Engine, create_engine

from app.core.config import get_settings


def get_engine() -> Engine | None:
    settings = get_settings()
    if not settings.database_url:
        return None
    return _get_engine_for_url(settings.database_url)


def check_database_connection() -> dict[str, object]:
    engine = get_engine()
    if engine is None:
        return {
            "connected": False,
            "reason": "DATABASE_URL is not configured",
        }

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        return {
            "connected": False,
            "reason": str(exc),
        }

    return {
        "connected": True,
        "reason": "ok",
    }


@lru_cache(maxsize=4)
def _get_engine_for_url(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)
