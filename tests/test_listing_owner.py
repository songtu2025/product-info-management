import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.modules.listing_owner import service
import pytest

from app.modules.listing_owner.service import (
    DuplicateListingOwnerError,
    ListingOwnerFilters,
    bulk_assign_listing_owner_from_products,
    build_create_payload,
    build_update_payload,
    create_listing_owner,
    update_listing_owner,
)


client = TestClient(app)


def test_listing_owner_list_renders_rows(monkeypatch):
    captured = {}

    def fake_list_listing_owners(filters):
        captured["filters"] = filters
        return {
            "rows": [
                {
                    "id": 1,
                    "store_site": "SAYOLA:US",
                    "listing": "RB833",
                    "owner": "张三",
                    "listing_status": "正常",
                    "listing_maintainer": "李四",
                    "include_inventory_age_assessment": "是",
                    "project_group": "项目组A",
                    "product_count": 2,
                    "updated_at": None,
                }
            ],
            "total": 51,
            "page": 2,
            "page_size": 50,
            "pages": 2,
        }

    monkeypatch.setattr(
        "app.modules.listing_owner.routes.list_listing_owners",
        fake_list_listing_owners,
    )

    response = client.get(
        "/listing-owners",
        params={"q": "RB", "page": "2", "page_size": "50"},
    )

    assert response.status_code == 200
    assert not isinstance(captured["filters"], str)
    assert captured["filters"].q == "RB"
    assert captured["filters"].page == 2
    assert captured["filters"].page_size == 50
    assert "SAYOLA:US" in response.text
    assert "RB833" in response.text
    assert "张三" in response.text
    assert "关联产品数" in response.text
    assert "2" in response.text
    assert "/?store_site=SAYOLA%3AUS&amp;listing=RB833" in response.text
    assert "查看产品" in response.text
    assert "共 51 条，每页 50 行，当前第 2 页" in response.text
    assert 'name="page_size"' in response.text
    assert "首页" in response.text
    assert "末页" in response.text
    assert "跳转" in response.text
    assert "q=RB&amp;page_size=50&amp;page=1" in response.text
    assert "/listing-owners/1/edit" in response.text
    assert "日志" in response.text
    assert "/operation-logs?table_name=amazon_listing_owner_config&amp;record_id=1" in response.text
    assert "/listing-owners/new" in response.text


def test_listing_owner_list_passes_structured_filters_and_renders_options(monkeypatch):
    captured = {}

    def fake_list_listing_owners(filters):
        captured["filters"] = filters
        return {
            "rows": [],
            "total": 0,
            "page": filters.page,
            "page_size": filters.page_size,
            "pages": 0,
        }

    monkeypatch.setattr(
        "app.modules.listing_owner.routes.list_listing_owners",
        fake_list_listing_owners,
    )
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_filter_options",
        lambda: {
            "store_sites": ["SAYOLA:US"],
            "owners": ["张三"],
            "listing_statuses": ["正常"],
            "listing_maintainers": ["李四"],
            "inventory_age_assessments": ["是"],
            "project_groups": ["项目组A"],
        },
    )

    response = client.get(
        "/listing-owners",
        params={
            "q": "RB",
            "store_site": "SAYOLA:US",
            "owner": "张三",
            "listing_status": "正常",
            "listing_maintainer": "李四",
            "include_inventory_age_assessment": "是",
            "project_group": "项目组A",
            "page": "2",
            "page_size": "50",
        },
    )

    assert response.status_code == 200
    assert captured["filters"].q == "RB"
    assert captured["filters"].store_site == "SAYOLA:US"
    assert captured["filters"].owner == "张三"
    assert captured["filters"].listing_status == "正常"
    assert captured["filters"].listing_maintainer == "李四"
    assert captured["filters"].include_inventory_age_assessment == "是"
    assert captured["filters"].project_group == "项目组A"
    assert "店铺站点" in response.text
    assert "负责人" in response.text
    assert "状态" in response.text
    assert "维护人" in response.text
    assert "纳入库龄考核" in response.text
    assert "项目组" in response.text
    assert 'option value="SAYOLA:US" selected' in response.text
    assert 'option value="张三" selected' in response.text
    assert "store_site=SAYOLA%3AUS" in response.text
    assert "include_inventory_age_assessment=%E6%98%AF" in response.text


def test_list_listing_owners_returns_paginated_filtered_page(monkeypatch):
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
                    project_group TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        for row_id in range(1, 52):
            conn.execute(
                text(
                    """
                    INSERT INTO amazon_listing_owner_config (
                        id, store_site, listing, owner, listing_status,
                        listing_maintainer, include_inventory_age_assessment, project_group, updated_at
                    )
                    VALUES (
                        :id, 'SAYOLA:US', :listing, :owner, '正常',
                        '李四', '是', '项目组A', '2026-06-04'
                    )
                    """
                ),
                {"id": row_id, "listing": f"RB{row_id:03d}", "owner": f"负责人{row_id}"},
            )
        conn.execute(
            text(
                """
                INSERT INTO amazon_listing_owner_config (
                    id, store_site, listing, owner, listing_status,
                    listing_maintainer, include_inventory_age_assessment, project_group, updated_at
                )
                VALUES (100, 'OTHER:US', 'XX1', '其他', '暂停', '赵六', '否', '项目组B', '2026-06-04')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    page = service.list_listing_owners(ListingOwnerFilters(q="RB", page=2, page_size=50))

    assert isinstance(page, dict)
    assert page["total"] == 51
    assert page["page"] == 2
    assert page["page_size"] == 50
    assert page["pages"] == 2
    assert [row["listing"] for row in page["rows"]] == ["RB051"]


def test_list_listing_owners_applies_structured_filters(monkeypatch):
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
                    project_group TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_listing_owner_config (
                    id, store_site, listing, owner, listing_status,
                    listing_maintainer, include_inventory_age_assessment, project_group, updated_at
                )
                VALUES
                    (1, 'SAYOLA:US', 'RB833', '张三', '正常', '李四', '是', '项目组A', '2026-06-04'),
                    (2, 'SAYOLA:US', 'RB832', '王五', '正常', '李四', '是', '项目组A', '2026-06-04'),
                    (3, 'OTHER:US', 'RB833', '张三', '暂停', '赵六', '否', '项目组B', '2026-06-04')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    page = service.list_listing_owners(
        ListingOwnerFilters(
            q="RB",
            store_site="SAYOLA:US",
            owner="张三",
            listing_status="正常",
            listing_maintainer="李四",
            include_inventory_age_assessment="是",
            project_group="项目组A",
        )
    )

    assert page["total"] == 1
    assert [row["id"] for row in page["rows"]] == [1]


def test_list_listing_owners_counts_linked_products(monkeypatch):
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
                    project_group TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY,
                    store_site TEXT,
                    listing TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_listing_owner_config (
                    id, store_site, listing, owner, listing_status,
                    listing_maintainer, include_inventory_age_assessment, project_group, updated_at
                )
                VALUES
                    (1, 'SAYOLA:US', 'RB833', '张三', '正常', '李四', '是', '项目组A', '2026-06-04'),
                    (2, 'SAYOLA:US', 'RB832', '王五', '正常', '李四', '是', '项目组A', '2026-06-04')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_product_info (id, store_site, listing)
                VALUES
                    (1, 'SAYOLA:US', 'RB833'),
                    (2, 'SAYOLA:US', 'RB833'),
                    (3, 'OTHER:US', 'RB833')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    page = service.list_listing_owners(ListingOwnerFilters())

    counts = {row["listing"]: row["product_count"] for row in page["rows"]}
    assert counts == {"RB832": 0, "RB833": 2}


def test_get_filter_options_returns_distinct_values(monkeypatch):
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
                    project_group TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_listing_owner_config (
                    id, store_site, listing, owner, listing_status,
                    listing_maintainer, include_inventory_age_assessment, project_group, updated_at
                )
                VALUES
                    (1, 'SAYOLA:US', 'RB833', '张三', '正常', '李四', '是', '项目组A', '2026-06-04'),
                    (2, 'SAYOLA:US', 'RB832', '张三', '正常', '李四', '是', '项目组A', '2026-06-04'),
                    (3, 'OTHER:US', 'RB831', '王五', '暂停', '赵六', '否', '项目组B', '2026-06-04')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    options = service.get_filter_options()

    assert options == {
        "store_sites": ["OTHER:US", "SAYOLA:US"],
        "owners": ["张三", "王五"],
        "listing_statuses": ["暂停", "正常"],
        "listing_maintainers": ["李四", "赵六"],
        "inventory_age_assessments": ["否", "是"],
        "project_groups": ["项目组A", "项目组B"],
    }


def test_get_filter_options_reuses_cached_values(monkeypatch):
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
                    project_group TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_listing_owner_config (
                    store_site, listing, owner, listing_status,
                    listing_maintainer, include_inventory_age_assessment, project_group
                )
                VALUES ('SAYOLA:US', 'RB833', '张三', '正常', '李四', '是', '项目组A')
                """
            )
        )

    connect_count = 0
    original_connect = engine.connect

    def counted_connect(*args, **kwargs):
        nonlocal connect_count
        connect_count += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(service, "get_engine", lambda: engine)
    monkeypatch.setattr(engine, "connect", counted_connect)
    service.clear_filter_options_cache()

    assert service.get_filter_options() == service.get_filter_options()
    assert connect_count == 1


def test_bulk_assign_listing_owner_from_products_creates_and_updates_configs(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY,
                    store_site TEXT,
                    listing TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE amazon_listing_owner_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    store_site TEXT,
                    listing TEXT,
                    owner TEXT,
                    listing_status TEXT,
                    listing_maintainer TEXT,
                    include_inventory_age_assessment TEXT,
                    project_group TEXT,
                    updated_at TEXT
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
                INSERT INTO amazon_product_info (id, store_site, listing)
                VALUES
                    (1, 'SAYOLA:US', 'RB833'),
                    (2, 'SAYOLA:US', 'RB832'),
                    (3, 'SAYOLA:US', NULL)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_listing_owner_config (
                    id, store_site, listing, owner, listing_status
                )
                VALUES (10, 'SAYOLA:US', 'RB833', '旧负责人', '正常')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    result = bulk_assign_listing_owner_from_products([1, 2, 3], "新负责人", changed_by="admin")

    assert result == {"created": 1, "updated": 1, "skipped": 1, "requested": 3}
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT store_site, listing, owner
                FROM amazon_listing_owner_config
                ORDER BY listing
                """
            )
        ).mappings().all()
        logs = conn.execute(
            text(
                """
                SELECT table_name, record_id, operation_type, changed_by, change_data
                FROM amazon_operation_log
                ORDER BY operation_type, record_id
                """
            )
        ).mappings().all()

    assert [dict(row) for row in rows] == [
        {"store_site": "SAYOLA:US", "listing": "RB832", "owner": "新负责人"},
        {"store_site": "SAYOLA:US", "listing": "RB833", "owner": "新负责人"},
    ]
    assert {log["operation_type"] for log in logs} == {"INSERT", "UPDATE"}
    assert all(log["table_name"] == "amazon_listing_owner_config" for log in logs)
    assert all(log["changed_by"] == "admin" for log in logs)
    assert any(
        json.loads(log["change_data"]) == {"owner": {"old": "旧负责人", "new": "新负责人"}}
        for log in logs
    )


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

    def fake_update_listing_owner(row_id, payload, changed_by="system"):
        captured["row_id"] = row_id
        captured["payload"] = payload
        captured["changed_by"] = changed_by
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
    assert captured["changed_by"] == "test-admin"


def test_listing_owner_new_page_renders_create_form(monkeypatch):
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_filter_options",
        lambda: {
            "store_sites": ["SAYOLA:US"],
            "owners": ["张三"],
            "listing_statuses": ["正常"],
            "listing_maintainers": ["李四"],
            "inventory_age_assessments": ["是"],
            "project_groups": ["项目组A"],
        },
    )

    response = client.get("/listing-owners/new")

    assert response.status_code == 200
    assert "新增 Listing 负责人" in response.text


def test_listing_owner_new_page_prefills_store_site_and_listing(monkeypatch):
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_filter_options",
        lambda: {
            "store_sites": ["SAYOLA:US"],
            "owners": [],
            "listing_statuses": [],
            "listing_maintainers": [],
            "inventory_age_assessments": [],
            "project_groups": [],
        },
    )

    response = client.get("/listing-owners/new?store_site=SAYOLA%3AUS&listing=ListingA")

    assert response.status_code == 200
    assert '<option value="SAYOLA:US" selected>SAYOLA:US</option>' in response.text
    assert 'name="listing" value="ListingA"' in response.text
    assert 'name="store_site"' in response.text
    assert 'option value="SAYOLA:US"' in response.text
    assert 'name="listing"' in response.text
    assert 'name="owner"' in response.text


def test_listing_owner_new_post_creates_and_redirects(monkeypatch):
    captured = {}

    def fake_create_listing_owner(payload, changed_by="system"):
        captured["payload"] = payload
        captured["changed_by"] = changed_by
        return 9

    monkeypatch.setattr(
        "app.modules.listing_owner.routes.create_listing_owner",
        fake_create_listing_owner,
    )

    response = client.post(
        "/listing-owners/new",
        data={
            "store_site": " SAYOLA:US ",
            "listing": " RB833 ",
            "owner": " 张三 ",
            "listing_status": "正常",
            "listing_maintainer": "",
            "include_inventory_age_assessment": "是",
            "project_group": " 项目组A ",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/listing-owners"
    assert captured == {
        "payload": {
            "store_site": "SAYOLA:US",
            "listing": "RB833",
            "owner": "张三",
            "listing_status": "正常",
            "listing_maintainer": None,
            "include_inventory_age_assessment": "是",
            "project_group": "项目组A",
        },
        "changed_by": "test-admin",
    }


def test_listing_owner_new_post_shows_duplicate_error(monkeypatch):
    def fake_create_listing_owner(payload, changed_by="system"):
        raise DuplicateListingOwnerError

    monkeypatch.setattr(
        "app.modules.listing_owner.routes.create_listing_owner",
        fake_create_listing_owner,
    )
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_filter_options",
        lambda: {
            "store_sites": ["SAYOLA:US"],
            "owners": [],
            "listing_statuses": [],
            "listing_maintainers": [],
            "inventory_age_assessments": [],
            "project_groups": [],
        },
    )

    response = client.post(
        "/listing-owners/new",
        data={"store_site": "SAYOLA:US", "listing": "RB833"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "负责人配置已存在" in response.text
    assert "SAYOLA:US" in response.text
    assert "RB833" in response.text


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


def test_build_listing_owner_create_payload_keeps_create_fields():
    payload = build_create_payload(
        {
            "store_site": " SAYOLA:US ",
            "listing": " RB833 ",
            "owner": " 张三 ",
            "listing_status": "",
            "listing_maintainer": "李四",
            "include_inventory_age_assessment": " 是 ",
            "project_group": "项目组A",
            "not_allowed": "ignored",
        }
    )

    assert payload == {
        "store_site": "SAYOLA:US",
        "listing": "RB833",
        "owner": "张三",
        "listing_status": None,
        "listing_maintainer": "李四",
        "include_inventory_age_assessment": "是",
        "project_group": "项目组A",
    }


def test_create_listing_owner_writes_operation_log(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_listing_owner_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    store_site TEXT NOT NULL,
                    listing TEXT NOT NULL,
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

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    row_id = create_listing_owner(
        {
            "store_site": "SAYOLA:US",
            "listing": "RB833",
            "owner": "张三",
            "listing_status": "正常",
            "listing_maintainer": None,
            "include_inventory_age_assessment": "是",
            "project_group": "项目组A",
        },
        changed_by="admin",
    )

    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM amazon_listing_owner_config")).mappings().one()
        log = conn.execute(text("SELECT * FROM amazon_operation_log")).mappings().one()

    assert row_id == 1
    assert row["store_site"] == "SAYOLA:US"
    assert row["listing"] == "RB833"
    assert log["table_name"] == "amazon_listing_owner_config"
    assert log["record_id"] == 1
    assert log["operation_type"] == "INSERT"
    assert log["changed_by"] == "admin"
    assert json.loads(log["change_data"]) == {
        "store_site": {"old": None, "new": "SAYOLA:US"},
        "listing": {"old": None, "new": "RB833"},
        "owner": {"old": None, "new": "张三"},
        "listing_status": {"old": None, "new": "正常"},
        "include_inventory_age_assessment": {"old": None, "new": "是"},
        "project_group": {"old": None, "new": "项目组A"},
    }


def test_create_listing_owner_rejects_duplicate_without_log(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_listing_owner_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    store_site TEXT NOT NULL,
                    listing TEXT NOT NULL,
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
                INSERT INTO amazon_listing_owner_config (store_site, listing, owner)
                VALUES ('SAYOLA:US', 'RB833', '张三')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    with pytest.raises(DuplicateListingOwnerError):
        create_listing_owner(
            {"store_site": "SAYOLA:US", "listing": "RB833", "owner": "王五"},
            changed_by="admin",
        )

    with engine.connect() as conn:
        row_count = conn.execute(text("SELECT COUNT(*) FROM amazon_listing_owner_config")).scalar_one()
        log_count = conn.execute(text("SELECT COUNT(*) FROM amazon_operation_log")).scalar_one()

    assert row_count == 1
    assert log_count == 0


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
