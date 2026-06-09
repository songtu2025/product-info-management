import json
import re
import time

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _product_list_config(response):
    match = re.search(
        r'<script id="product-list-config" type="application/json">\s*(.*?)\s*</script>',
        response.text,
        re.S,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_product_list_renders_rows_and_pagination(monkeypatch):
    def fake_list_products(filters):
        assert filters.page == 1
        assert filters.page_size == 20
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
            "page_size": 20,
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
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_product_quality_summary",
        lambda: {"total": 2634, "quality_issue_total": 10},
    )

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
    assert "运营概览" in response.text
    assert "产品总数" in response.text
    assert "2634" in response.text
    assert "数据质量问题" in response.text
    assert "10" in response.text
    assert "当前筛选" in response.text
    assert 'data-bulk-product-id="7"' in response.text
    assert "批量锁仓" in response.text
    assert "批量解锁" in response.text
    assert "批量设置负责人" in response.text
    assert 'placeholder="输入负责人"' in response.text
    assert 'name="owner"' in response.text


def test_product_list_uses_lightweight_quality_summary(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {
            "rows": [],
            "total": 3,
            "page": 1,
            "page_size": 20,
            "pages": 1,
        },
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {
            "store_sites": [],
            "brands": [],
            "sales_statuses": [],
            "listings": [],
            "listing_owners": [],
            "listing_owner_statuses": [],
            "project_groups": [],
        },
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_product_quality_summary",
        lambda: {"total": 2634, "quality_issue_total": 10},
        raising=False,
    )

    def full_report_should_not_run():
        raise AssertionError("product list should not load the full quality report")

    monkeypatch.setattr(
        "app.modules.product_info.routes.get_product_quality_report",
        full_report_should_not_run,
        raising=False,
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "2634" in response.text
    assert "10" in response.text


def test_product_list_loads_independent_context_in_parallel(monkeypatch):
    def slow_list_products(filters):
        time.sleep(0.12)
        return {
            "rows": [],
            "total": 3,
            "page": 1,
            "page_size": 20,
            "pages": 1,
        }

    def slow_filter_options():
        time.sleep(0.12)
        return {
            "store_sites": [],
            "brands": [],
            "sales_statuses": [],
            "listings": [],
            "listing_owners": [],
            "listing_owner_statuses": [],
            "project_groups": [],
        }

    def slow_quality_summary():
        time.sleep(0.12)
        return {"total": 2634, "quality_issue_total": 10}

    def slow_preferences(username, keys):
        time.sleep(0.12)
        return {}

    monkeypatch.setattr("app.modules.product_info.routes.list_products", slow_list_products)
    monkeypatch.setattr("app.modules.product_info.routes.get_filter_options", slow_filter_options)
    monkeypatch.setattr("app.modules.product_info.routes.get_product_quality_summary", slow_quality_summary)
    monkeypatch.setattr("app.modules.product_info.routes.get_user_preferences", slow_preferences)

    start = time.perf_counter()
    response = client.get("/")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert elapsed < 0.35


def test_product_bulk_lock_post_updates_selected_products(monkeypatch):
    captured = {}

    def fake_bulk_update(product_ids, lock_status, changed_by="system"):
        captured["product_ids"] = product_ids
        captured["lock_status"] = lock_status
        captured["changed_by"] = changed_by
        return {"updated": 2, "requested": 2}

    monkeypatch.setattr("app.modules.product_info.routes.bulk_update_product_lock_status", fake_bulk_update)

    response = client.post(
        "/products/bulk-lock",
        data={"product_ids": ["7", "8"], "lock_status": "锁"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert captured == {
        "product_ids": [7, 8],
        "lock_status": "锁",
        "changed_by": "test-admin",
    }


def test_product_bulk_lock_post_rejects_missing_selection():
    response = client.post(
        "/products/bulk-lock",
        data={"lock_status": "锁"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_product_bulk_listing_owner_post_assigns_owner(monkeypatch):
    captured = {}
    cache_cleared = {"called": False}

    def fake_bulk_assign(product_ids, owner, changed_by="system"):
        captured["product_ids"] = product_ids
        captured["owner"] = owner
        captured["changed_by"] = changed_by
        return {"created": 1, "updated": 1, "skipped": 0, "requested": 2}

    def fake_clear_product_list_cache():
        cache_cleared["called"] = True

    monkeypatch.setattr(
        "app.modules.product_info.routes.bulk_assign_listing_owner_from_products",
        fake_bulk_assign,
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.clear_product_list_cache",
        fake_clear_product_list_cache,
    )

    response = client.post(
        "/products/bulk-listing-owner",
        data={"product_ids": ["7", "8"], "owner": "新负责人"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert captured == {
        "product_ids": [7, 8],
        "owner": "新负责人",
        "changed_by": "test-admin",
    }
    assert cache_cleared["called"]


def test_product_list_uses_lightweight_table_columns(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {
            "rows": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
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
    assert 'src="http://testserver/static/js/product-list.js?v=export-fields-modal"' in response.text
    assert '"storageKey": "productListColumnState"' in response.text

    visible_columns = [
        "msku",
        "asin",
        "store_site",
        "product_name",
        "sku",
        "brand",
        "sales_status",
        "listing",
        "listing_owner",
        "listing_owner_status",
        "project_group",
        "updated_at",
    ]
    for column in visible_columns:
        assert f'data-column="{column}"' in response.text
        assert f'data-column-toggle="{column}"' in response.text
        assert f'data-resize-column="{column}"' in response.text
        assert f'data-column-setting-item="{column}"' in response.text
        assert f'data-column-drag-handle="{column}"' in response.text

    for hidden_detail_column in [
        "parent_asin",
        "fnsku",
        "storage_type",
        "category_level_1",
        "category_a",
        "category_b",
        "label_name",
        "msku_shipping_remark",
        "transfer_remark",
        "msku_lock_status",
        "created_at",
    ]:
        assert f'data-column="{hidden_detail_column}"' not in response.text
        assert f'data-column-toggle="{hidden_detail_column}"' not in response.text

    assert 'data-export-field="parent_asin"' in response.text
    assert 'data-export-field="msku_shipping_remark"' in response.text
    assert 'data-column="actions"' in response.text
    assert 'data-column-toggle="actions"' not in response.text
    assert "data-column-order-up" not in response.text
    assert "data-column-order-down" not in response.text
    assert 'data-default-visible="false"' not in response.text
    assert 'draggable="true"' in response.text
    assert "autoFitColumnWidths" not in response.text
    assert "min-width: 1120px" not in response.text


def test_partial_product_list_returns_content_fragment(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 20, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    response = client.get("/", headers={"x-partial-request": "1"})

    assert response.status_code == 200
    assert "<!doctype html>" not in response.text
    assert "app-sidebar" not in response.text
    assert "筛选产品" in response.text


def test_product_list_exposes_export_field_controls(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {
            "rows": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "pages": 0,
        },
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    response = client.get("/")

    assert response.status_code == 200
    assert re.search(r'data-export-download[\s\S]*?>导出</a>', response.text)
    assert "选择字段导出" not in response.text
    assert "导出当前结果" not in response.text
    assert "选择导出字段" in response.text
    assert "data-export-fields-button" not in response.text
    assert "data-export-fields-modal" in response.text
    assert "data-export-fields-panel" in response.text
    assert "data-export-fields-confirm" in response.text
    assert "data-export-fields-cancel" in response.text
    assert 'data-list-action-group="export"' in response.text
    assert 'data-list-action-group="bulk"' in response.text
    assert 'data-list-action-group="manage"' in response.text
    assert "data-list-bulk-owner-controls" in response.text
    assert "批量设置负责人" in response.text
    assert 'aria-label="批量设置负责人"' in response.text
    assert 'placeholder="输入负责人"' in response.text
    assert ">批量负责人</button>" not in response.text
    assert 'name="export_fields"' in response.text
    assert 'value="msku"' in response.text
    assert 'value="storage_type"' in response.text
    assert 'href="/products/export/import-compatible"' in response.text
    assert "导入兼容导出" in response.text
    assert 'src="http://testserver/static/js/product-list.js?v=export-fields-modal"' in response.text


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
            "listing_owner": "OwnerA",
            "listing_owner_status": "Active",
            "project_group": "GroupA",
            "page": "2",
        },
    )

    assert response.status_code == 200
    assert captured["filters"].q == "abc"
    assert captured["filters"].store_site == "SAYOLA:US"
    assert captured["filters"].brand == "BrandA"
    assert captured["filters"].sales_status == "在售"
    assert captured["filters"].listing == "ListingA"
    assert captured["filters"].listing_owner == "OwnerA"
    assert captured["filters"].listing_owner_status == "Active"
    assert captured["filters"].project_group == "GroupA"
    assert captured["filters"].page == 2
    assert captured["filters"].page_size == 20


def test_product_list_renders_clear_filter_link(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 20, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {
            "store_sites": [],
            "brands": [],
            "sales_statuses": [],
            "listings": [],
            "listing_owners": [],
            "listing_owner_statuses": [],
            "project_groups": [],
        },
    )

    response = client.get("/?q=abc&brand=BrandA&listing=ListingA&page=2")

    assert response.status_code == 200
    assert "清空筛选" in response.text
    assert 'data-clear-product-filters' in response.text
    assert 'href="/"' in response.text
    assert 'data-clear-product-filters href="/?"' not in response.text


def test_product_list_renders_active_filter_summary(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 20, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {
            "store_sites": ["SAYOLA:US"],
            "brands": ["BrandA"],
            "sales_statuses": ["在售"],
            "listings": ["ListingA"],
            "listing_owners": ["OwnerA"],
            "listing_owner_statuses": ["Active"],
            "project_groups": ["GroupA"],
        },
    )

    response = client.get(
        "/",
        params={
            "q": "abc",
            "store_site": "SAYOLA:US",
            "brand": "BrandA",
            "sales_status": "在售",
            "listing": "ListingA",
            "listing_owner": "OwnerA",
            "listing_owner_status": "Active",
            "project_group": "GroupA",
            "page_size": "100",
        },
    )

    assert response.status_code == 200
    assert 'data-active-product-filters' in response.text
    assert "已筛选" in response.text
    assert "关键词：abc" in response.text
    assert "店铺站点：SAYOLA:US" in response.text
    assert "品牌：BrandA" in response.text
    assert "销售状态：在售" in response.text
    assert "Listing：ListingA" in response.text
    assert "负责人：OwnerA" in response.text
    assert "Listing 状态：Active" in response.text
    assert "项目组：GroupA" in response.text
    assert "每页行数：100" not in response.text


def test_product_list_hides_active_filter_summary_without_filters(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 20, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {
            "store_sites": [],
            "brands": [],
            "sales_statuses": [],
            "listings": [],
            "listing_owners": [],
            "listing_owner_statuses": [],
            "project_groups": [],
        },
    )

    response = client.get("/")

    assert response.status_code == 200
    assert 'data-active-product-filters' not in response.text


def test_product_list_passes_page_size_and_keeps_it_in_pagination(monkeypatch):
    captured = {}

    def fake_list_products(filters):
        captured["filters"] = filters
        return {
            "rows": [],
            "total": 250,
            "page": filters.page,
            "page_size": filters.page_size,
            "pages": 3,
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
            "brand": "BrandA",
            "page": "2",
            "page_size": "100",
        },
    )

    assert response.status_code == 200
    assert captured["filters"].page == 2
    assert captured["filters"].page_size == 100
    assert 'name="page_size"' in response.text
    assert 'value="100" selected' in response.text
    assert "q=abc&amp;brand=BrandA&amp;page_size=100&amp;page=1" in response.text
    assert "q=abc&amp;brand=BrandA&amp;page_size=100&amp;page=3" in response.text


def test_product_list_loads_saved_column_state(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 50, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    def fake_get_preferences(username, keys):
        captured.append((username, tuple(keys)))
        return {
            "product_info.list.columns": {
                "visible": {"id": True},
                "order": ["id", "msku"],
                "widths": {"id": 88},
            }
        }

    monkeypatch.setattr("app.modules.product_info.routes.get_user_preferences", fake_get_preferences)

    response = client.get("/")

    assert response.status_code == 200
    assert captured == [
        (
            "test-admin",
            (
                "product_info.export.fields",
                "product_info.list.columns",
                "product_info.filter.views",
            ),
        )
    ]
    config = _product_list_config(response)
    assert config["columnState"] == {
        "visible": {"id": True},
        "order": ["id", "msku"],
        "widths": {"id": 88},
    }


def test_product_list_loads_saved_export_fields(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 50, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    def fake_get_preferences(username, keys):
        captured.append((username, tuple(keys)))
        return {"product_info.export.fields": {"fields": ["msku", "storage_type"]}}

    monkeypatch.setattr("app.modules.product_info.routes.get_user_preferences", fake_get_preferences)

    response = client.get("/")

    assert response.status_code == 200
    assert captured == [
        (
            "test-admin",
            (
                "product_info.export.fields",
                "product_info.list.columns",
                "product_info.filter.views",
            ),
        )
    ]
    config = _product_list_config(response)
    assert config["savedExportFields"] == ["msku", "storage_type"]


def test_product_list_loads_saved_filter_views(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 20, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    def fake_get_preferences(username, keys):
        captured.append((username, tuple(keys)))
        return {
            "product_info.filter.views": {
                "views": [
                    {
                        "name": "在售 OwnerA",
                        "filters": {
                            "sales_status": "在售",
                            "listing_owner": "OwnerA",
                            "page_size": 100,
                        },
                    }
                ]
            }
        }

    monkeypatch.setattr("app.modules.product_info.routes.get_user_preferences", fake_get_preferences)

    response = client.get("/")

    assert response.status_code == 200
    assert captured == [
        (
            "test-admin",
            (
                "product_info.export.fields",
                "product_info.list.columns",
                "product_info.filter.views",
            ),
        )
    ]
    assert "常用筛选" in response.text
    assert "在售 OwnerA" in response.text
    assert "sales_status=%E5%9C%A8%E5%94%AE&amp;listing_owner=OwnerA&amp;page_size=100" in response.text
    config = _product_list_config(response)
    assert config["filterViewState"] == [
        {
            "name": "在售 OwnerA",
            "filters": {
                "sales_status": "在售",
                "listing_owner": "OwnerA",
                "page_size": 100,
            },
            "url": "/?sales_status=%E5%9C%A8%E5%94%AE&listing_owner=OwnerA&page_size=100",
        }
    ]


def test_product_column_preference_save_persists_for_current_user(monkeypatch):
    captured = {}

    def fake_save_preference(username, key, value):
        captured["username"] = username
        captured["key"] = key
        captured["value"] = value
        return True

    monkeypatch.setattr("app.modules.product_info.routes.save_user_preference", fake_save_preference)

    response = client.post(
        "/products/preferences/columns",
        json={"visible": {"id": True}, "order": ["id", "msku"], "widths": {"id": 88}},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured == {
        "username": "test-admin",
        "key": "product_info.list.columns",
        "value": {"visible": {"id": True}, "order": ["id", "msku"], "widths": {"id": 88}},
    }


def test_product_export_field_preference_save_persists_for_current_user(monkeypatch):
    captured = {}

    def fake_save_preference(username, key, value):
        captured["username"] = username
        captured["key"] = key
        captured["value"] = value
        return True

    monkeypatch.setattr("app.modules.product_info.routes.save_user_preference", fake_save_preference)

    response = client.post(
        "/products/preferences/export-fields",
        json={"fields": ["msku", "storage_type", "not_a_column"]},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured == {
        "username": "test-admin",
        "key": "product_info.export.fields",
        "value": {"fields": ["msku", "storage_type"]},
    }


def test_product_filter_view_preference_save_persists_safe_views(monkeypatch):
    captured = {}

    def fake_save_preference(username, key, value):
        captured["username"] = username
        captured["key"] = key
        captured["value"] = value
        return True

    monkeypatch.setattr("app.modules.product_info.routes.save_user_preference", fake_save_preference)

    response = client.post(
        "/products/preferences/filter-views",
        json={
            "views": [
                {
                    "name": "  在售 OwnerA  ",
                    "filters": {
                        "q": "abc",
                        "sales_status": "在售",
                        "listing_owner": "OwnerA",
                        "page_size": 100,
                        "page": 9,
                        "bad": "drop",
                    },
                },
                {"name": "", "filters": {"brand": "BrandA"}},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured == {
        "username": "test-admin",
        "key": "product_info.filter.views",
        "value": {
            "views": [
                {
                    "name": "在售 OwnerA",
                    "filters": {
                        "q": "abc",
                        "sales_status": "在售",
                        "listing_owner": "OwnerA",
                        "page_size": 100,
                    },
                }
            ]
        },
    }


def test_product_export_passes_filters_and_returns_xlsx(monkeypatch):
    captured = {}

    def fake_export_products(filters, export_fields=None):
        captured["filters"] = filters
        captured["export_fields"] = export_fields
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
            "listing_owner": "OwnerA",
            "listing_owner_status": "Active",
            "project_group": "GroupA",
            "page": "4",
            "export_fields": ["msku", "storage_type"],
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
    assert captured["filters"].listing_owner == "OwnerA"
    assert captured["filters"].listing_owner_status == "Active"
    assert captured["filters"].project_group == "GroupA"
    assert captured["filters"].page == 1
    assert captured["export_fields"] == ["msku", "storage_type"]


def test_product_import_compatible_export_passes_filters_and_returns_xlsx(monkeypatch):
    captured = {}

    def fake_export_products(filters):
        captured["filters"] = filters
        return b"import-compatible-xlsx"

    monkeypatch.setattr(
        "app.modules.product_info.routes.export_products_for_import_to_xlsx",
        fake_export_products,
        raising=False,
    )

    response = client.get(
        "/products/export/import-compatible",
        params={
            "q": "abc",
            "store_site": "SAYOLA:US",
            "brand": "BrandA",
            "sales_status": "在售",
            "listing": "ListingA",
            "listing_owner": "OwnerA",
            "listing_owner_status": "Active",
            "project_group": "GroupA",
            "page": "4",
            "export_fields": ["msku", "storage_type"],
        },
    )

    assert response.status_code == 200
    assert response.content == b"import-compatible-xlsx"
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment;" in response.headers["content-disposition"]
    assert captured["filters"].q == "abc"
    assert captured["filters"].store_site == "SAYOLA:US"
    assert captured["filters"].brand == "BrandA"
    assert captured["filters"].sales_status == "在售"
    assert captured["filters"].listing == "ListingA"
    assert captured["filters"].listing_owner == "OwnerA"
    assert captured["filters"].listing_owner_status == "Active"
    assert captured["filters"].project_group == "GroupA"
    assert captured["filters"].page == 1
