from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_product_list_renders_rows_and_pagination(monkeypatch):
    def fake_list_products(filters):
        assert filters.page == 1
        assert filters.page_size == 50
        return {
            "rows": [
                {
                    "id": 7,
                    "msku": "MSKU-001",
                    "asin": "B012345678",
                    "store_site": "SAYOLA:US",
                    "product_name": "Test Product",
                    "sku": "SKU-001",
                    "brand": "BrandA",
                    "listing": "ListingA",
                    "sales_status": "在售",
                    "updated_at": None,
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 50,
            "pages": 1,
        }

    def fake_get_filter_options():
        return {
            "store_sites": ["SAYOLA:US"],
            "brands": ["BrandA"],
            "sales_statuses": ["在售"],
            "listings": ["ListingA"],
        }

    monkeypatch.setattr("app.modules.product_info.routes.list_products", fake_list_products)
    monkeypatch.setattr("app.modules.product_info.routes.get_filter_options", fake_get_filter_options)

    response = client.get("/")

    assert response.status_code == 200
    assert "MSKU-001" in response.text
    assert "SAYOLA:US" in response.text
    assert "共 1 条" in response.text


def test_product_list_passes_search_and_filter_params(monkeypatch):
    captured = {}

    def fake_list_products(filters):
        captured["filters"] = filters
        return {
            "rows": [],
            "total": 0,
            "page": filters.page,
            "page_size": filters.page_size,
            "pages": 0,
        }

    monkeypatch.setattr("app.modules.product_info.routes.list_products", fake_list_products)
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    response = client.get(
        "/",
        params={
            "q": "abc",
            "store_site": "SAYOLA:US",
            "brand": "BrandA",
            "sales_status": "在售",
            "listing": "ListingA",
            "page": "2",
        },
    )

    assert response.status_code == 200
    assert captured["filters"].q == "abc"
    assert captured["filters"].store_site == "SAYOLA:US"
    assert captured["filters"].brand == "BrandA"
    assert captured["filters"].sales_status == "在售"
    assert captured["filters"].listing == "ListingA"
    assert captured["filters"].page == 2
    assert captured["filters"].page_size == 50
