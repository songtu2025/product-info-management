from app.core.db import get_engine


def test_get_engine_reuses_engine_for_same_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV_FILE", "__missing_test_env_file__")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    first = get_engine()
    second = get_engine()

    assert first is second
