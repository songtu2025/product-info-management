import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.modules.operation_log import service
from app.modules.operation_log.service import (
    OperationLogFilters,
    format_change_items,
    get_operation_log_page,
    list_operation_logs,
)


client = TestClient(app)


def test_format_change_items_turns_json_into_readable_rows():
    items = format_change_items(
        json.dumps(
            {
                "product_name": {"old": "旧名称", "new": "新名称"},
                "brand": {"old": None, "new": "RIVBOS"},
            },
            ensure_ascii=False,
        )
    )

    assert items == [
        {"field": "product_name", "old": "旧名称", "new": "新名称"},
        {"field": "brand", "old": None, "new": "RIVBOS"},
    ]


def test_operation_log_list_filters_rows(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
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
                INSERT INTO amazon_operation_log (
                    table_name, record_id, operation_type, changed_by, change_data
                )
                VALUES
                ('amazon_product_info', 7, 'UPDATE', 'system', :product_change),
                ('amazon_store_site', 1, 'UPDATE', 'system', :store_change)
                """
            ),
            {
                "product_change": json.dumps(
                    {"product_name": {"old": "旧名称", "new": "新名称"}},
                    ensure_ascii=False,
                ),
                "store_change": json.dumps(
                    {"domain": {"old": "amazon.com", "new": "amazon.ca"}},
                    ensure_ascii=False,
                ),
            },
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    rows = list_operation_logs(
        OperationLogFilters(table_name="amazon_product_info", record_id=7)
    )

    assert len(rows) == 1
    assert rows[0]["table_name"] == "amazon_product_info"
    assert rows[0]["record_id"] == 7
    assert rows[0]["change_items"] == [
        {"field": "product_name", "old": "旧名称", "new": "新名称"}
    ]


def test_get_operation_log_page_filters_by_user_date_and_paginates(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
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
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_operation_log (
                    table_name, record_id, operation_type, changed_by, change_data, created_at
                )
                VALUES
                ('amazon_product_info', 1, 'UPDATE', 'alice', '{}', '2026-06-01 10:00:00'),
                ('amazon_product_info', 2, 'UPDATE', 'alice', '{}', '2026-06-02 10:00:00'),
                ('amazon_product_info', 3, 'UPDATE', 'alice', '{}', '2026-06-03 10:00:00'),
                ('amazon_product_info', 4, 'UPDATE', 'bob', '{}', '2026-06-02 11:00:00')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    page = get_operation_log_page(
        OperationLogFilters(
            table_name="amazon_product_info",
            changed_by="alice",
            start_date="2026-06-01",
            end_date="2026-06-03",
            page=2,
            page_size=1,
        )
    )

    assert page["total"] == 3
    assert page["page"] == 2
    assert page["pages"] == 3
    assert [row["record_id"] for row in page["rows"]] == [2]


def test_operation_log_page_renders_change_items(monkeypatch):
    monkeypatch.setattr(
        "app.modules.operation_log.routes.get_operation_log_page",
        lambda filters: {
            "rows": [
                {
                    "id": 1,
                    "table_name": "amazon_product_info",
                    "record_id": 7,
                    "operation_type": "UPDATE",
                    "changed_by": "system",
                    "created_at": "2026-06-01 12:00:00",
                    "change_items": [
                        {"field": "product_name", "old": "旧名称", "new": "新名称"}
                    ],
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 50,
            "pages": 1,
        },
    )

    response = client.get("/operation-logs")

    assert response.status_code == 200
    assert "amazon_product_info" in response.text
    assert "product_name" in response.text
    assert "旧名称" in response.text
    assert "新名称" in response.text


def test_operation_log_page_keeps_new_filter_values(monkeypatch):
    captured = {}

    def fake_page(filters):
        captured["filters"] = filters
        return {"rows": [], "total": 0, "page": 1, "page_size": 50, "pages": 0}

    monkeypatch.setattr("app.modules.operation_log.routes.get_operation_log_page", fake_page)

    response = client.get(
        "/operation-logs?changed_by=alice&start_date=2026-06-01&end_date=2026-06-03&page_size=100"
    )

    assert response.status_code == 200
    assert captured["filters"].changed_by == "alice"
    assert captured["filters"].start_date == "2026-06-01"
    assert captured["filters"].end_date == "2026-06-03"
    assert captured["filters"].page_size == 100
    assert 'name="changed_by" value="alice"' in response.text
    assert 'name="start_date" value="2026-06-01"' in response.text
    assert 'name="end_date" value="2026-06-03"' in response.text
