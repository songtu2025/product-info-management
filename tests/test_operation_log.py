import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.modules.operation_log import service
from app.modules.operation_log.service import (
    OperationLogFilters,
    format_change_items,
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


def test_operation_log_page_renders_change_items(monkeypatch):
    monkeypatch.setattr(
        "app.modules.operation_log.routes.list_operation_logs",
        lambda filters: [
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
    )

    response = client.get("/operation-logs")

    assert response.status_code == 200
    assert "amazon_product_info" in response.text
    assert "product_name" in response.text
    assert "旧名称" in response.text
    assert "新名称" in response.text
