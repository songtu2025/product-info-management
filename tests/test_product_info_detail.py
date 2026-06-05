from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_product_detail_renders_product_store_and_owner(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_product_detail",
        lambda product_id: {
            "product": {
                "id": product_id,
                "msku": "MSKU-001",
                "asin": "B012345678",
                "store_site": "SAYOLA:US",
                "parent_asin": "B0PARENT",
                "product_name": "Test Product",
                "sku": "SKU-001",
                "brand": "BrandA",
                "fnsku": "FNSKU-001",
                "listing": "ListingA",
                "sales_status": "在售",
                "storage_type": "FBA",
                "category_level_1": "服饰",
                "category_a": "眼镜",
                "category_b": "太阳镜",
                "label_name": "核心款",
                "msku_shipping_remark": "发货备注",
                "transfer_remark": "借调备注",
                "msku_lock_status": "否",
                "created_at": "2026-06-01 10:00:00",
                "updated_at": "2026-06-02 10:00:00",
            },
            "store_site": {
                "store_site": "SAYOLA:US",
                "store": "SAYOLA",
                "country": "US",
                "domain": "amazon.com",
            },
            "owner": {
                "owner": "张三",
                "listing_status": "正常",
                "listing_maintainer": "李四",
                "include_inventory_age_assessment": "是",
                "project_group": "项目组A",
            },
        },
    )

    response = client.get("/products/7")

    assert response.status_code == 200
    assert "关键定位字段" in response.text
    assert "基础信息" in response.text
    assert "运营维护" in response.text
    assert "备注信息" in response.text
    assert "MSKU-001" in response.text
    assert "Test Product" in response.text
    assert "FNSKU-001" in response.text
    assert "太阳镜" in response.text
    assert "amazon.com" in response.text
    assert "张三" in response.text
    assert "发货备注" in response.text
    assert "查看操作日志" in response.text
    assert "/operation-logs?table_name=amazon_product_info&amp;record_id=7" in response.text


def test_product_detail_links_to_create_listing_owner_when_missing(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_product_detail",
        lambda product_id: {
            "product": {
                "id": product_id,
                "msku": "MSKU-001",
                "store_site": "SAYOLA:US",
                "listing": "ListingA",
                "product_name": "Test Product",
            },
            "store_site": None,
            "owner": None,
        },
    )

    response = client.get("/products/7")

    assert response.status_code == 200
    assert "创建负责人配置" in response.text
    assert "/listing-owners/new?store_site=SAYOLA%3AUS&amp;listing=ListingA" in response.text


def test_product_detail_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_product_detail",
        lambda product_id: None,
    )

    response = client.get("/products/999999")

    assert response.status_code == 404
