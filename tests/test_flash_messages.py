from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _product_detail(product_id: int):
    return {
        "product": {
            "id": product_id,
            "msku": "MSKU-001",
            "store_site": "SAYOLA:US",
            "listing": "RB833",
            "product_name": "Product",
        },
        "store_site": None,
        "owner": None,
    }


def test_product_edit_success_flash_is_shown_once(monkeypatch):
    monkeypatch.setattr("app.modules.product_info.routes.get_product_detail", _product_detail)
    monkeypatch.setattr("app.modules.product_info.routes.update_product", lambda product_id, payload, changed_by="system": True)

    response = client.post(
        "/products/7/edit",
        data={"product_name": "New Product"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "产品信息已保存。" in response.text
    assert 'class="flash-message"' in response.text

    refreshed = client.get("/products/7")

    assert refreshed.status_code == 200
    assert "产品信息已保存。" not in refreshed.text


def test_store_site_success_flash_on_list(monkeypatch):
    monkeypatch.setattr("app.modules.store_site.routes.get_store_site", lambda store_site_id: {"id": store_site_id, "store_site": "SAYOLA:US"})
    monkeypatch.setattr("app.modules.store_site.routes.update_store_site", lambda store_site_id, payload, changed_by="system": True)
    monkeypatch.setattr("app.modules.store_site.routes.list_store_sites", lambda q=None: [])

    response = client.post(
        "/store-sites/1/edit",
        data={"store": "SAYOLA"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "店铺站点已保存。" in response.text


def test_listing_owner_success_flash_on_list(monkeypatch):
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_listing_owner",
        lambda row_id: {"id": row_id, "store_site": "SAYOLA:US", "listing": "RB833"},
    )
    monkeypatch.setattr("app.modules.listing_owner.routes.update_listing_owner", lambda row_id, payload, changed_by="system": True)
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.list_listing_owners",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 50, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_filter_options",
        lambda: {
            "store_sites": [],
            "owners": [],
            "listing_statuses": [],
            "listing_maintainers": [],
            "inventory_age_assessments": [],
            "project_groups": [],
        },
    )

    response = client.post(
        "/listing-owners/1/edit",
        data={"owner": "张三"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Listing 负责人已保存。" in response.text


def test_admin_user_success_flash_on_list(monkeypatch):
    monkeypatch.setattr("app.modules.admin_user.routes.create_admin_user", lambda payload, changed_by="system": True)
    monkeypatch.setattr("app.modules.admin_user.routes.list_admin_users", lambda: [])

    response = client.post(
        "/admin-users/new",
        data={"username": "new_user", "password": "aa123123", "role": "viewer", "is_active": "1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "用户已新增。" in response.text
