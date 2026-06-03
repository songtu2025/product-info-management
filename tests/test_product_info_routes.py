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
    assert 'href="/products/7">MSKU-001</a>' not in response.text
    assert 'href="/products/7/edit">MSKU-001</a>' not in response.text
    assert "SAYOLA:US" in response.text
    assert "共 1 条" in response.text
    assert "操作" in response.text
    assert "详情" in response.text
    assert "日志" in response.text
    assert "/products/7" in response.text
    assert "/operation-logs?table_name=amazon_product_info&amp;record_id=7" in response.text
    assert "/products/7/edit" in response.text


def test_product_list_exposes_column_customization_controls(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {
            "rows": [],
            "total": 0,
            "page": 1,
            "page_size": 50,
            "pages": 0,
        },
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "字段设置" in response.text
    assert "productListColumnState" in response.text

    for column in [
        "id",
        "msku",
        "asin",
        "store_site",
        "parent_asin",
        "product_name",
        "sku",
        "brand",
        "fnsku",
        "listing",
        "sales_status",
        "storage_type",
        "category_level_1",
        "category_a",
        "category_b",
        "label_name",
        "msku_shipping_remark",
        "transfer_remark",
        "msku_lock_status",
        "created_at",
        "updated_at",
    ]:
        assert f'data-column="{column}"' in response.text
        assert f'data-column-toggle="{column}"' in response.text
        assert f'data-resize-column="{column}"' in response.text
        assert f'data-column-setting-item="{column}"' in response.text
        assert f'data-column-drag-handle="{column}"' in response.text

    assert 'data-column="actions"' in response.text
    assert 'data-column-toggle="actions"' not in response.text
    assert "data-column-order-up" not in response.text
    assert "data-column-order-down" not in response.text
    assert 'data-default-visible="false"' in response.text
    assert 'draggable="true"' in response.text
    assert "autoFitColumnWidths" in response.text
    assert "min-width: 1120px" not in response.text


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


def test_product_export_passes_filters_and_returns_xlsx(monkeypatch):
    captured = {}

    def fake_export_products(filters):
        captured["filters"] = filters
        return b"xlsx-bytes"

    monkeypatch.setattr(
        "app.modules.product_info.routes.export_products_to_xlsx",
        fake_export_products,
    )

    response = client.get(
        "/products/export",
        params={
            "q": "abc",
            "store_site": "SAYOLA:US",
            "brand": "BrandA",
            "sales_status": "在售",
            "listing": "ListingA",
            "page": "4",
        },
    )

    assert response.status_code == 200
    assert response.content == b"xlsx-bytes"
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment;" in response.headers["content-disposition"]
    assert captured["filters"].q == "abc"
    assert captured["filters"].store_site == "SAYOLA:US"
    assert captured["filters"].brand == "BrandA"
    assert captured["filters"].sales_status == "在售"
    assert captured["filters"].listing == "ListingA"
    assert captured["filters"].page == 1
