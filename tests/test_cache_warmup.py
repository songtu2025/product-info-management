from fastapi.testclient import TestClient

from app.core import warmup
from app.main import app


def test_warm_product_info_caches_calls_page_dependencies(monkeypatch):
    calls = []

    monkeypatch.setattr(
        warmup,
        "list_products",
        lambda filters: calls.append(("list_products", filters.page, filters.page_size)),
    )
    monkeypatch.setattr(
        warmup,
        "get_filter_options",
        lambda: calls.append(("get_filter_options",)),
    )
    monkeypatch.setattr(
        warmup,
        "get_product_quality_summary",
        lambda: calls.append(("get_product_quality_summary",)),
    )
    monkeypatch.setattr(
        warmup,
        "get_user_preferences",
        lambda username, keys: calls.append(("get_user_preferences", username, tuple(keys))),
    )

    warmup.warm_product_info_caches()

    assert calls == [
        ("list_products", 1, 20),
        ("get_filter_options",),
        ("get_product_quality_summary",),
        (
            "get_user_preferences",
            "admin",
            (
                "product_info.export.fields",
                "product_info.list.columns",
                "product_info.filter.views",
            ),
        ),
        (
            "get_user_preferences",
            "test-admin",
            (
                "product_info.export.fields",
                "product_info.list.columns",
                "product_info.filter.views",
            ),
        ),
    ]


def test_app_lifespan_warms_product_info_caches(monkeypatch):
    calls = []

    monkeypatch.setattr("app.main.warm_product_info_caches", lambda: calls.append("warm"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert calls == ["warm"]
