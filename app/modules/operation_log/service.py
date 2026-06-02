import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.core.db import get_engine


@dataclass(frozen=True)
class OperationLogFilters:
    table_name: str | None = None
    record_id: int | None = None
    operation_type: str | None = None


def list_operation_logs(filters: OperationLogFilters) -> list[dict[str, object]]:
    engine = get_engine()
    if engine is None:
        return []

    where_sql, params = _build_where(filters)
    sql = text(
        f"""
        SELECT
            id,
            table_name,
            record_id,
            operation_type,
            changed_by,
            change_data,
            created_at
        FROM amazon_operation_log
        {where_sql}
        ORDER BY id DESC
        LIMIT 200
        """
    )

    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, params).mappings()]

    for row in rows:
        row["change_items"] = format_change_items(row.get("change_data"))
    return rows


def format_change_items(change_data: Any) -> list[dict[str, Any]]:
    if not change_data:
        return []

    if isinstance(change_data, str):
        try:
            change_data = json.loads(change_data)
        except json.JSONDecodeError:
            return []

    if not isinstance(change_data, dict):
        return []

    items = []
    for field, values in change_data.items():
        if not isinstance(values, dict):
            continue
        items.append(
            {
                "field": field,
                "old": values.get("old"),
                "new": values.get("new"),
            }
        )
    return items


def _build_where(filters: OperationLogFilters) -> tuple[str, dict[str, object]]:
    clauses = []
    params: dict[str, object] = {}

    table_name = _clean(filters.table_name)
    operation_type = _clean(filters.operation_type)

    if table_name:
        clauses.append("table_name = :table_name")
        params["table_name"] = table_name
    if filters.record_id is not None:
        clauses.append("record_id = :record_id")
        params["record_id"] = filters.record_id
    if operation_type:
        clauses.append("operation_type = :operation_type")
        params["operation_type"] = operation_type

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
