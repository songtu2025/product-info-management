import json

from sqlalchemy import text

from app.core.db import get_engine


def get_user_preference(username: str, preference_key: str) -> dict[str, object] | None:
    engine = get_engine()
    if engine is None:
        return None

    with engine.begin() as conn:
        _ensure_table(conn)
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


def save_user_preference(username: str, preference_key: str, value: dict[str, object]) -> bool:
    engine = get_engine()
    if engine is None:
        return False

    with engine.begin() as conn:
        _ensure_table(conn)
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
    return True


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
