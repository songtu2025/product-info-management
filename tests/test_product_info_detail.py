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
                "product_name": "Test Product",
                "sku": "SKU-001",
                "brand": "BrandA",
                "listing": "ListingA",
                "sales_status": "在售",
                "label_name": "核心款",
                "msku_shipping_remark": "发货备注",
                "transfer_remark": "借调备注",
                "msku_lock_status": "否",
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
    assert "MSKU-001" in response.text
    assert "Test Product" in response.text
    assert "amazon.com" in response.text
    assert "张三" in response.text
    assert "发货备注" in response.text


def test_product_detail_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_product_detail",
        lambda product_id: None,
    )

    response = client.get("/products/999999")

    assert response.status_code == 404
