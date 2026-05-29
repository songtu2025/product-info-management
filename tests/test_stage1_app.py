from fastapi.testclient import TestClient

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
