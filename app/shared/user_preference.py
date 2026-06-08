import json
from time import monotonic

from sqlalchemy import bindparam
from sqlalchemy import text

from app.core.db import get_engine


_ENSURED_TABLE_ENGINE_IDS: set[int] = set()
USER_PREFERENCE_CACHE_TTL_SECONDS = 60
_user_preference_cache: dict[tuple[object, ...], dict[str, object]] = {}


def get_user_preference(username: str, preference_key: str) -> dict[str, object] | None:
    engine = get_engine()
    if engine is None:
        return None

    with engine.begin() as conn:
        _ensure_table_once(conn, engine)
        row = conn.execute(
            text(
                """
                SELECT preference_value
                FROM amazon_user_preference
                WHERE username = :username
                    AND preference_key = :preference_key
                """
            ),
            {"username": username, "preference_key": preference_key},
        ).mappings().first()

    if row is None:
        return None
    value = json.loads(row["preference_value"])
    return value if isinstance(value, dict) else None


def get_user_preferences(username: str, preference_keys: list[str] | tuple[str, ...]) -> dict[str, dict[str, object]]:
    keys = [key for key in preference_keys if key]
    if not keys:
        return {}

    engine = get_engine()
    if engine is None:
        return {}
    cache_key = _preference_cache_key(engine, username, keys)
    now = monotonic()
    cached = _user_preference_cache.get(cache_key)
    if cached and now < cached["expires_at"]:
        return cached["value"]

    query = text(
        """
        SELECT preference_key, preference_value
        FROM amazon_user_preference
        WHERE username = :username
            AND preference_key IN :preference_keys
        """
    ).bindparams(bindparam("preference_keys", expanding=True))

    with engine.begin() as conn:
        _ensure_table_once(conn, engine)
        rows = list(
            conn.execute(
                query,
                {"username": username, "preference_keys": keys},
            ).mappings()
        )

    preferences = {}
    for row in rows:
        value = json.loads(row["preference_value"])
        if isinstance(value, dict):
            preferences[row["preference_key"]] = value
    _user_preference_cache[cache_key] = {
        "expires_at": now + USER_PREFERENCE_CACHE_TTL_SECONDS,
        "value": preferences,
    }
    return preferences


def save_user_preference(username: str, preference_key: str, value: dict[str, object]) -> bool:
    engine = get_engine()
    if engine is None:
        return False

    with engine.begin() as conn:
        _ensure_table_once(conn, engine)
        conn.execute(
            text(
                """
                DELETE FROM amazon_user_preference
                WHERE username = :username
                    AND preference_key = :preference_key
                """
            ),
            {"username": username, "preference_key": preference_key},
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_user_preference (
                    username,
                    preference_key,
                    preference_value
                )
                VALUES (
                    :username,
                    :preference_key,
                    :preference_value
                )
                """
            ),
            {
                "username": username,
                "preference_key": preference_key,
                "preference_value": json.dumps(value, ensure_ascii=False),
            },
        )
    clear_user_preference_cache(username)
    return True


def clear_user_preference_cache(username: str | None = None) -> None:
    if username is None:
        _user_preference_cache.clear()
        return
    stale_keys = [key for key in _user_preference_cache if key[1] == username]
    for key in stale_keys:
        _user_preference_cache.pop(key, None)


def _preference_cache_key(engine, username: str, preference_keys: list[str]) -> tuple[object, ...]:
    return (id(engine), username, *sorted(set(preference_keys)))


def _ensure_table_once(conn, engine) -> None:
    engine_id = id(engine)
    if engine_id in _ENSURED_TABLE_ENGINE_IDS:
        return
    _ensure_table(conn)
    _ENSURED_TABLE_ENGINE_IDS.add(engine_id)


def _ensure_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS amazon_user_preference (
                username VARCHAR(64) NOT NULL,
                preference_key VARCHAR(128) NOT NULL,
                preference_value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (username, preference_key)
            )
            """
        )
    )
