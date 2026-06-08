from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.core import security
from app.main import app


client = TestClient(app)


def setup_auth_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE amazon_operation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    operation_type TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    change_data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_admin_user (id, username, password_hash, role, is_active)
                VALUES
                    (1, 'admin', :admin_hash, 'admin', 1),
                    (2, 'viewer', :viewer_hash, 'viewer', 1)
                """
            ),
            {
                "admin_hash": security.hash_password("admin-pass"),
                "viewer_hash": security.hash_password("viewer-pass"),
            },
        )

    monkeypatch.setattr(security, "get_engine", lambda: engine)
    return engine


def test_login_page_is_public(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False

    response = client.get("/login")

    assert response.status_code == 200
    assert "登录" in response.text
    assert "https://cdn.tailwindcss.com" not in response.text
    assert 'href="http://testserver/static/css/tailwind-lite.css"' in response.text
    assert 'href="http://testserver/static/css/app.css"' in response.text


def test_unauthenticated_backend_redirects_to_login(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_admin_login_allows_backend_access(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 50, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    login = client.post(
        "/login",
        data={"username": "admin", "password": "admin-pass"},
        follow_redirects=False,
    )
    response = client.get("/")

    assert login.status_code == 303
    assert response.status_code == 200
    assert "admin" in response.text
    assert "退出登录" in response.text
    assert "/logout" in response.text
    assert "/admin-users" in response.text
    assert "/products/import" in response.text
    assert "/account/password" in response.text


def test_change_password_page_requires_login(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    response = client.get("/account/password", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_logged_in_user_can_change_own_password(monkeypatch):
    engine = setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )

    page = client.get("/account/password")
    response = client.post(
        "/account/password",
        data={
            "current_password": "viewer-pass",
            "new_password": "viewer-new-pass",
            "confirm_password": "viewer-new-pass",
        },
        follow_redirects=False,
    )

    assert page.status_code == 200
    assert "修改密码" in page.text
    assert response.status_code == 303
    assert response.headers["location"] == "/account/password"

    client.get("/logout", follow_redirects=False)
    old_login = client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )
    new_login = client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-new-pass"},
        follow_redirects=False,
    )

    assert old_login.status_code == 400
    assert new_login.status_code == 303
    with engine.connect() as conn:
        log = conn.execute(
            text("SELECT table_name, operation_type, changed_by, change_data FROM amazon_operation_log")
        ).mappings().one()
    assert log["table_name"] == "amazon_admin_user"
    assert log["operation_type"] == "CHANGE_PASSWORD"
    assert log["changed_by"] == "viewer"
    assert "viewer-new-pass" not in log["change_data"]


def test_change_password_rejects_wrong_current_password(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )
    response = client.post(
        "/account/password",
        data={
            "current_password": "bad-pass",
            "new_password": "viewer-new-pass",
            "confirm_password": "viewer-new-pass",
        },
    )

    assert response.status_code == 400
    assert "原密码不正确" in response.text


def test_viewer_cannot_use_admin_import_page(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )
    response = client.get("/products/import", follow_redirects=False)

    assert response.status_code == 403


def test_viewer_cannot_use_admin_import_actions(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )

    template_response = client.get("/products/import/template", follow_redirects=False)
    preview_response = client.post(
        "/products/import/preview",
        files={"file": ("products.xlsx", b"not-xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        follow_redirects=False,
    )
    commit_response = client.post(
        "/products/import/commit",
        data={"import_token": "token-1"},
        follow_redirects=False,
    )

    assert template_response.status_code == 403
    assert preview_response.status_code == 403
    assert commit_response.status_code == 403


def test_viewer_cannot_use_admin_user_page(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )
    response = client.get("/admin-users", follow_redirects=False)

    assert response.status_code == 403


def test_viewer_cannot_access_write_pages_directly(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )

    paths = [
        "/products/new",
        "/products/1/edit",
        "/store-sites/new",
        "/store-sites/1/edit",
        "/listing-owners/new",
        "/listing-owners/1/edit",
        "/admin-users/new",
        "/admin-users/1/edit",
        "/admin-users/1/reset-password",
    ]

    for path in paths:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 403, path


def test_viewer_cannot_post_write_actions_directly(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )

    requests = [
        ("/products/new", {"store_site": "SAYOLA:US", "msku": "MSKU-1"}),
        ("/products/1/edit", {"product_name": "changed"}),
        ("/products/bulk-lock", {"product_ids": ["1"], "lock_status": "锁"}),
        ("/products/bulk-listing-owner", {"product_ids": ["1"], "owner": "张三"}),
        ("/store-sites/new", {"store_site": "SAYOLA:US"}),
        ("/store-sites/1/edit", {"store": "changed"}),
        ("/listing-owners/new", {"store_site": "SAYOLA:US", "listing": "RB833"}),
        ("/listing-owners/1/edit", {"owner": "changed"}),
        ("/admin-users/new", {"username": "new", "password": "pass", "role": "viewer"}),
        ("/admin-users/1/edit", {"role": "viewer"}),
        ("/admin-users/1/reset-password", {"password": "new-pass"}),
    ]

    for path, data in requests:
        response = client.post(path, data=data, follow_redirects=False)
        assert response.status_code == 403, path


def test_viewer_can_export_products(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()
    monkeypatch.setattr(
        "app.modules.product_info.routes.export_products_to_xlsx",
        lambda filters: b"xlsx",
    )

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )
    response = client.get("/products/export")

    assert response.status_code == 200


def test_viewer_does_not_see_admin_navigation(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {
            "rows": [
                {
                    "id": 1,
                    "msku": "MSKU-1",
                    "asin": "B001",
                    "store_site": "SAYOLA:US",
                    "product_name": "Product 1",
                    "sku": "SKU-1",
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
        },
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )
    response = client.get("/")

    assert response.status_code == 200
    assert "/admin-users" not in response.text
    assert "/products/import" not in response.text
    assert 'href="/products/1">MSKU-1</a>' not in response.text
    assert "/products/1" in response.text
    assert "/operation-logs?table_name=amazon_product_info&amp;record_id=1" in response.text
    assert "/products/1/edit" not in response.text


def test_viewer_does_not_see_product_edit_entry(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_product_detail",
        lambda product_id: {
            "product": {
                "id": product_id,
                "msku": "MSKU-1",
                "product_name": "Product 1",
            },
            "store_site": None,
            "owner": None,
        },
    )

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )
    response = client.get("/products/1")

    assert response.status_code == 200
    assert "/products/1/edit" not in response.text


def test_viewer_does_not_see_config_edit_entries(monkeypatch):
    setup_auth_db(monkeypatch)
    app.state.disable_auth = False
    client.cookies.clear()
    monkeypatch.setattr(
        "app.modules.store_site.routes.list_store_sites",
        lambda q=None: [
            {
                "id": 1,
                "store_site": "SAYOLA:US",
                "store": "SAYOLA",
                "country": "US",
                "domain": "amazon.com",
                "updated_at": None,
            }
        ],
    )
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.list_listing_owners",
        lambda q=None: [
            {
                "id": 1,
                "store_site": "SAYOLA:US",
                "listing": "A",
                "owner": "owner",
                "listing_status": "active",
                "listing_maintainer": "owner",
                "include_inventory_age_assessment": "yes",
                "project_group": "G1",
                "updated_at": None,
            }
        ],
    )

    client.post(
        "/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )

    store_response = client.get("/store-sites")
    owner_response = client.get("/listing-owners")

    assert store_response.status_code == 200
    assert owner_response.status_code == 200
    assert "/store-sites/1/edit" not in store_response.text
    assert "/listing-owners/1/edit" not in owner_response.text
