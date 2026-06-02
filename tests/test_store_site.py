import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.modules.store_site import service
from app.modules.store_site.service import build_update_payload, update_store_site


client = TestClient(app)


def test_store_site_list_renders_rows(monkeypatch):
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

    response = client.get("/store-sites")

    assert response.status_code == 200
    assert "SAYOLA:US" in response.text
    assert "amazon.com" in response.text
    assert "/store-sites/1/edit" in response.text


def test_store_site_edit_page_does_not_allow_store_site_key_edit(monkeypatch):
    monkeypatch.setattr(
        "app.modules.store_site.routes.get_store_site",
        lambda store_site_id: {
            "id": store_site_id,
            "store_site": "SAYOLA:US",
            "store": "SAYOLA",
            "country": "US",
            "domain": "amazon.com",
        },
    )

    response = client.get("/store-sites/1/edit")

    assert response.status_code == 200
    assert "SAYOLA:US" in response.text
    assert "name=\"store\"" in response.text
    assert "name=\"country\"" in response.text
    assert "name=\"domain\"" in response.text
    assert "name=\"store_site\"" not in response.text


def test_store_site_edit_post_updates_and_redirects(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.modules.store_site.routes.get_store_site",
        lambda store_site_id: {
            "id": store_site_id,
            "store_site": "SAYOLA:US",
            "store": "SAYOLA",
            "country": "US",
            "domain": "amazon.com",
        },
    )

    def fake_update_store_site(store_site_id, payload):
        captured["store_site_id"] = store_site_id
        captured["payload"] = payload
        return True

    monkeypatch.setattr("app.modules.store_site.routes.update_store_site", fake_update_store_site)

    response = client.post(
        "/store-sites/1/edit",
        data={
            "store": "SAYOLA-NEW",
            "country": "CA",
            "domain": "amazon.ca",
            "store_site": "SHOULD-NOT-CHANGE",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/store-sites"
    assert captured["store_site_id"] == 1
    assert captured["payload"] == {
        "store": "SAYOLA-NEW",
        "country": "CA",
        "domain": "amazon.ca",
    }


def test_build_store_site_update_payload_keeps_only_editable_fields():
    payload = build_update_payload(
        {
            "store": " SAYOLA ",
            "country": "",
            "domain": " amazon.com ",
            "store_site": "SHOULD-NOT-CHANGE",
        }
    )

    assert payload == {
        "store": "SAYOLA",
        "country": None,
        "domain": "amazon.com",
    }


def test_update_store_site_writes_operation_log(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_store_site (
                    id INTEGER PRIMARY KEY,
                    store_site TEXT,
                    store TEXT,
                    country TEXT,
                    domain TEXT
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
                INSERT INTO amazon_store_site (id, store_site, store, country, domain)
                VALUES (1, 'SAYOLA:US', 'SAYOLA', 'US', 'amazon.com')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert update_store_site(1, {"store": "SAYOLA-NEW", "country": "US"})

    with engine.connect() as conn:
        store = conn.execute(text("SELECT store FROM amazon_store_site WHERE id = 1")).scalar_one()
        log = conn.execute(text("SELECT * FROM amazon_operation_log")).mappings().one()

    assert store == "SAYOLA-NEW"
    assert log["table_name"] == "amazon_store_site"
    assert log["record_id"] == 1
    assert json.loads(log["change_data"]) == {
        "store": {"old": "SAYOLA", "new": "SAYOLA-NEW"}
    }
