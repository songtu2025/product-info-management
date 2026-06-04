from sqlalchemy import create_engine
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
