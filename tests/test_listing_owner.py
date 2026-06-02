import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.modules.listing_owner import service
from app.modules.listing_owner.service import build_update_payload, update_listing_owner


client = TestClient(app)


def test_listing_owner_list_renders_rows(monkeypatch):
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.list_listing_owners",
        lambda q=None: [
            {
                "id": 1,
                "store_site": "SAYOLA:US",
                "listing": "RB833",
                "owner": "张三",
                "listing_status": "正常",
                "listing_maintainer": "李四",
                "include_inventory_age_assessment": "是",
                "project_group": "项目组A",
                "updated_at": None,
            }
        ],
    )

    response = client.get("/listing-owners")

    assert response.status_code == 200
    assert "SAYOLA:US" in response.text
    assert "RB833" in response.text
    assert "张三" in response.text
    assert "/listing-owners/1/edit" in response.text


def test_listing_owner_edit_page_does_not_allow_key_edit(monkeypatch):
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_listing_owner",
        lambda row_id: {
            "id": row_id,
            "store_site": "SAYOLA:US",
            "listing": "RB833",
            "owner": "张三",
            "listing_status": "正常",
            "listing_maintainer": "李四",
            "include_inventory_age_assessment": "是",
            "project_group": "项目组A",
        },
    )

    response = client.get("/listing-owners/1/edit")

    assert response.status_code == 200
    assert "SAYOLA:US" in response.text
    assert "RB833" in response.text
    assert "name=\"owner\"" in response.text
    assert "name=\"listing_status\"" in response.text
    assert "name=\"store_site\"" not in response.text
    assert "name=\"listing\"" not in response.text


def test_listing_owner_edit_post_updates_and_redirects(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_listing_owner",
        lambda row_id: {
            "id": row_id,
            "store_site": "SAYOLA:US",
            "listing": "RB833",
            "owner": "张三",
            "listing_status": "正常",
            "listing_maintainer": "李四",
            "include_inventory_age_assessment": "是",
            "project_group": "项目组A",
        },
    )

    def fake_update_listing_owner(row_id, payload):
        captured["row_id"] = row_id
        captured["payload"] = payload
        return True

    monkeypatch.setattr(
        "app.modules.listing_owner.routes.update_listing_owner",
        fake_update_listing_owner,
    )

    response = client.post(
        "/listing-owners/1/edit",
        data={
            "owner": "王五",
            "listing_status": "暂停",
            "listing_maintainer": "赵六",
            "include_inventory_age_assessment": "否",
            "project_group": "项目组B",
            "store_site": "SHOULD-NOT-CHANGE",
            "listing": "SHOULD-NOT-CHANGE",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/listing-owners"
    assert captured["row_id"] == 1
    assert captured["payload"] == {
        "owner": "王五",
        "listing_status": "暂停",
        "listing_maintainer": "赵六",
        "include_inventory_age_assessment": "否",
        "project_group": "项目组B",
    }


def test_build_listing_owner_update_payload_keeps_only_editable_fields():
    payload = build_update_payload(
        {
            "owner": " 王五 ",
            "listing_status": "",
            "listing_maintainer": "赵六",
            "include_inventory_age_assessment": "否",
            "project_group": " 项目组B ",
            "store_site": "SHOULD-NOT-CHANGE",
            "listing": "SHOULD-NOT-CHANGE",
        }
    )

    assert payload == {
        "owner": "王五",
        "listing_status": None,
        "listing_maintainer": "赵六",
        "include_inventory_age_assessment": "否",
        "project_group": "项目组B",
    }


def test_update_listing_owner_writes_operation_log(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_listing_owner_config (
                    id INTEGER PRIMARY KEY,
                    store_site TEXT,
                    listing TEXT,
                    owner TEXT,
                    listing_status TEXT,
                    listing_maintainer TEXT,
                    include_inventory_age_assessment TEXT,
                    project_group TEXT
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
                INSERT INTO amazon_listing_owner_config (
                    id, store_site, listing, owner, listing_status,
                    listing_maintainer, include_inventory_age_assessment, project_group
                )
                VALUES (1, 'SAYOLA:US', 'RB833', '张三', '正常', '李四', '是', '项目组A')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert update_listing_owner(1, {"owner": "王五", "listing_status": "正常"})

    with engine.connect() as conn:
        owner = conn.execute(
            text("SELECT owner FROM amazon_listing_owner_config WHERE id = 1")
        ).scalar_one()
        log = conn.execute(text("SELECT * FROM amazon_operation_log")).mappings().one()

    assert owner == "王五"
    assert log["table_name"] == "amazon_listing_owner_config"
    assert log["record_id"] == 1
    assert json.loads(log["change_data"]) == {
        "owner": {"old": "张三", "new": "王五"}
    }
