from fastapi.testclient import TestClient

from app.main import app
from app.modules.product_info.service import (
    DuplicateProductError,
    build_create_payload,
    build_update_payload,
)


client = TestClient(app)


def fake_detail(product_id: int):
    return {
        "product": {
            "id": product_id,
            "msku": "MSKU-001",
            "asin": "B012345678",
            "store_site": "SAYOLA:US",
            "product_name": "Old Product",
            "sku": "SKU-001",
            "brand": "BrandA",
            "listing": "ListingA",
            "sales_status": "在售",
            "storage_type": "FBA",
            "category_level_1": "服饰",
            "category_a": "眼镜",
            "category_b": "太阳镜",
            "label_name": "旧标签",
            "msku_shipping_remark": "旧发货备注",
            "transfer_remark": "旧借调备注",
            "msku_lock_status": "否",
        },
        "store_site": None,
        "owner": None,
    }


def test_product_edit_page_renders_allowed_fields(monkeypatch):
    monkeypatch.setattr("app.modules.product_info.routes.get_product_detail", fake_detail)

    response = client.get("/products/7/edit")

    assert response.status_code == 200
    assert "Old Product" in response.text
    assert "name=\"product_name\"" in response.text
    assert "name=\"sales_status\"" in response.text
    assert "name=\"msku\"" not in response.text
    assert "name=\"store_site\"" not in response.text


def test_product_new_page_renders_create_fields(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_store_sites",
        lambda: [
            {"store_site": "SAYOLA:US"},
            {"store_site": "RIVBOS:CA"},
        ],
    )

    response = client.get("/products/new")

    assert response.status_code == 200
    assert "新增产品信息" in response.text
    assert "<select" in response.text
    assert "name=\"store_site\"" in response.text
    assert "SAYOLA:US" in response.text
    assert "RIVBOS:CA" in response.text
    assert "name=\"msku\"" in response.text
    assert "name=\"asin\"" in response.text
    assert "name=\"listing\"" in response.text
    assert "name=\"product_name\"" in response.text


def test_product_new_post_creates_and_redirects(monkeypatch):
    captured = {}

    def fake_create_product(payload, changed_by="system"):
        captured["payload"] = payload
        captured["changed_by"] = changed_by
        return 9

    monkeypatch.setattr("app.modules.product_info.routes.create_product", fake_create_product)

    response = client.post(
        "/products/new",
        data={
            "store_site": " SAYOLA:US ",
            "msku": " MSKU-NEW ",
            "asin": "B012345678",
            "listing": "ListingA",
            "product_name": "New Product",
            "brand": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/products/9"
    assert captured["changed_by"] == "test-admin"
    assert captured["payload"] == {
        "store_site": "SAYOLA:US",
        "msku": "MSKU-NEW",
        "asin": "B012345678",
        "listing": "ListingA",
        "product_name": "New Product",
        "brand": None,
    }


def test_product_new_post_shows_duplicate_product_error(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_store_sites",
        lambda: [
            {"store_site": "SAYOLA:US"},
            {"store_site": "RIVBOS:CA"},
        ],
    )

    def fake_create_product(payload, changed_by="system"):
        raise DuplicateProductError

    monkeypatch.setattr("app.modules.product_info.routes.create_product", fake_create_product)

    response = client.post(
        "/products/new",
        data={"store_site": "SAYOLA:US", "msku": "MSKU-001"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "该店铺站点下 MSKU 已存在" in response.text
    assert '<option value="SAYOLA:US" selected>SAYOLA:US</option>' in response.text
    assert "MSKU-001" in response.text


def test_product_edit_post_updates_and_redirects(monkeypatch):
    captured = {}
    monkeypatch.setattr("app.modules.product_info.routes.get_product_detail", fake_detail)

    def fake_update_product(product_id, payload, changed_by="system"):
        captured["product_id"] = product_id
        captured["payload"] = payload
        captured["changed_by"] = changed_by
        return True

    monkeypatch.setattr("app.modules.product_info.routes.update_product", fake_update_product)

    response = client.post(
        "/products/7/edit",
        data={
            "product_name": "New Product",
            "brand": "BrandB",
            "sales_status": "停售",
            "storage_type": "FBA",
            "category_level_1": "服饰",
            "category_a": "眼镜",
            "category_b": "太阳镜",
            "label_name": "新标签",
            "msku_shipping_remark": "新发货备注",
            "transfer_remark": "新借调备注",
            "msku_lock_status": "是",
            "msku": "SHOULD-NOT-BE-UPDATED",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/products/7"
    assert captured["product_id"] == 7
    assert captured["payload"]["product_name"] == "New Product"
    assert captured["changed_by"] == "test-admin"
    assert "msku" not in captured["payload"]


def test_build_update_payload_keeps_only_editable_fields():
    payload = build_update_payload(
        {
            "product_name": "  New Product  ",
            "brand": "BrandB",
            "msku": "SHOULD-NOT-BE-UPDATED",
            "store_site": "SHOULD-NOT-BE-UPDATED",
            "label_name": "",
        }
    )

    assert payload == {
        "product_name": "New Product",
        "brand": "BrandB",
        "label_name": None,
    }


def test_build_create_payload_keeps_product_fields_and_requires_keys():
    payload = build_create_payload(
        {
            "store_site": " SAYOLA:US ",
            "msku": " MSKU-NEW ",
            "asin": "",
            "listing": "ListingA",
            "product_name": "New Product",
            "not_allowed": "ignored",
        }
    )

    assert payload == {
        "store_site": "SAYOLA:US",
        "msku": "MSKU-NEW",
        "asin": None,
        "listing": "ListingA",
        "product_name": "New Product",
    }
