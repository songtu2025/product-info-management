from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.pool import StaticPool


def test_user_preference_round_trips_json_state(monkeypatch):
    from app.shared import user_preference

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(user_preference, "get_engine", lambda: engine)

    value = {
        "visible": {"id": True},
        "order": ["id", "msku"],
        "widths": {"id": 88},
    }

    assert user_preference.save_user_preference("admin", "product_info.list.columns", value)
    assert user_preference.get_user_preference("admin", "product_info.list.columns") == value
    assert user_preference.get_user_preference("viewer", "product_info.list.columns") is None


def test_user_preference_ensures_table_once(monkeypatch):
    from app.shared import user_preference

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(user_preference, "get_engine", lambda: engine)

    statements = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.split()))

    assert user_preference.get_user_preference("admin", "missing") is None
    assert user_preference.get_user_preference("admin", "missing") is None

    create_table_count = sum(
        statement.startswith("CREATE TABLE IF NOT EXISTS amazon_user_preference")
        for statement in statements
    )
    assert create_table_count == 1


def test_user_preferences_load_multiple_keys(monkeypatch):
    from app.shared import user_preference

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(user_preference, "get_engine", lambda: engine)

    user_preference.save_user_preference("admin", "columns", {"visible": {"id": True}})
    user_preference.save_user_preference("admin", "export", {"fields": ["msku"]})

    assert user_preference.get_user_preferences("admin", ["columns", "export", "missing"]) == {
        "columns": {"visible": {"id": True}},
        "export": {"fields": ["msku"]},
    }


def test_user_preferences_reuses_cached_values(monkeypatch):
    from app.shared import user_preference

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(user_preference, "get_engine", lambda: engine)
    user_preference.clear_user_preference_cache()
    user_preference.save_user_preference("admin", "columns", {"visible": {"id": True}})

    connect_count = 0
    original_begin = engine.begin

    def counted_begin(*args, **kwargs):
        nonlocal connect_count
        connect_count += 1
        return original_begin(*args, **kwargs)

    monkeypatch.setattr(engine, "begin", counted_begin)

    assert user_preference.get_user_preferences("admin", ["columns"]) == {
        "columns": {"visible": {"id": True}}
    }
    assert user_preference.get_user_preferences("admin", ["columns"]) == {
        "columns": {"visible": {"id": True}}
    }
    assert connect_count == 1
