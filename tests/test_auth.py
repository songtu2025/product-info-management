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
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 50, "pages": 0},
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
