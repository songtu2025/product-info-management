from fastapi.testclient import TestClient
from pathlib import Path

from app.core.config import get_settings
from app.main import app


client = TestClient(app)


def test_home_page_renders_admin_shell(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 50, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "Amazon 运营数据管理后台" in response.text
    assert "产品信息" in response.text
    assert "店铺站点" in response.text
    assert "Listing 负责人" in response.text
    assert 'data-app-content' in response.text
    assert 'data-partial-nav' in response.text
    assert "https://cdn.tailwindcss.com" not in response.text
    assert 'href="http://testserver/static/css/tailwind-lite.css"' in response.text
    assert 'href="http://testserver/static/css/app.css"' in response.text
    assert 'src="http://testserver/static/js/partial-nav.js"' in response.text


def test_tailwind_cdn_is_replaced_by_local_utility_css():
    tailwind_lite = Path("app/static/css/tailwind-lite.css")

    assert tailwind_lite.exists()

    css = tailwind_lite.read_text(encoding="utf-8")
    for selector in [
        ".flex",
        ".grid",
        ".hidden",
        ".min-h-screen",
        ".text-slate-900",
        ".px-5",
        ".py-5",
        ".md\\:grid-cols-3",
        ".lg\\:grid-cols-7",
        ".lg\\:block",
    ]:
        assert selector in css


def test_frontend_behavior_uses_static_javascript_files():
    partial_nav = Path("app/static/js/partial-nav.js")
    product_list = Path("app/static/js/product-list.js")
    partial_nav_js = partial_nav.read_text(encoding="utf-8")

    assert partial_nav.exists()
    assert product_list.exists()
    assert "x-partial-request" in partial_nav_js
    assert "product-list-config" in product_list.read_text(encoding="utf-8")


def test_partial_navigation_guards_downloads_and_stale_responses():
    partial_nav_js = Path("app/static/js/partial-nav.js").read_text(encoding="utf-8")

    assert "content-type" in partial_nav_js
    assert "text/html" in partial_nav_js
    assert "latestRequestId" in partial_nav_js
    assert "requestId !== latestRequestId" in partial_nav_js


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "amazon-ops-admin"}


def test_db_status_without_database_url_is_explicitly_unconfigured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV_FILE", "__missing_test_env_file__")

    response = client.get("/db/status")

    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert response.json()["reason"] == "DATABASE_URL is not configured"


def test_settings_loads_database_url_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=mysql+pymysql://user:pass@example.com:3306/amazon_ops?charset=utf8mb4\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV_FILE", str(env_file))

    settings = get_settings()

    assert settings.database_url == "mysql+pymysql://user:pass@example.com:3306/amazon_ops?charset=utf8mb4"
