import json
from dataclasses import dataclass
from math import ceil
from typing import Any

from sqlalchemy import text

from app.core.db import get_engine


@dataclass(frozen=True)
class OperationLogFilters:
    table_name: str | None = None
    record_id: int | None = None
    operation_type: str | None = None
    changed_by: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    page: int = 1
    page_size: int = 50


def list_operation_logs(filters: OperationLogFilters) -> list[dict[str, object]]:
    return get_operation_log_page(filters)["rows"]


def get_operation_log_page(filters: OperationLogFilters) -> dict[str, object]:
    engine = get_engine()
    if engine is None:
        return _empty_page(filters)

    filters = _normalize_filters(filters)
    where_sql, params = _build_where(filters)
    offset = (filters.page - 1) * filters.page_size
    params.update({"limit": filters.page_size, "offset": offset})
    count_sql = text(f"SELECT COUNT(*) FROM amazon_operation_log {where_sql}")
    list_sql = text(
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
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar_one()
        rows = [dict(row) for row in conn.execute(list_sql, params).mappings()]

    for row in rows:
        row["change_items"] = format_change_items(row.get("change_data"))

    pages = ceil(total / filters.page_size) if total else 0
    return {
        "rows": rows,
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size,
        "pages": pages,
    }


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
    changed_by = _clean(filters.changed_by)
    start_date = _clean(filters.start_date)
    end_date = _clean(filters.end_date)

    if table_name:
        clauses.append("table_name = :table_name")
        params["table_name"] = table_name
    if filters.record_id is not None:
        clauses.append("record_id = :record_id")
        params["record_id"] = filters.record_id
    if operation_type:
        clauses.append("operation_type = :operation_type")
        params["operation_type"] = operation_type
    if changed_by:
        clauses.append("changed_by = :changed_by")
        params["changed_by"] = changed_by
    if start_date:
        clauses.append("created_at >= :start_date")
        params["start_date"] = start_date
    if end_date:
        clauses.append("created_at <= :end_date")
        params["end_date"] = f"{end_date} 23:59:59" if len(end_date) == 10 else end_date

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_filters(filters: OperationLogFilters) -> OperationLogFilters:
    page_size = filters.page_size if 1 <= filters.page_size <= 200 else 50
    page = filters.page if filters.page > 0 else 1
    return OperationLogFilters(
        table_name=_clean(filters.table_name),
        record_id=filters.record_id,
        operation_type=_clean(filters.operation_type),
        changed_by=_clean(filters.changed_by),
        start_date=_clean(filters.start_date),
        end_date=_clean(filters.end_date),
        page=page,
        page_size=page_size,
    )


def _empty_page(filters: OperationLogFilters) -> dict[str, object]:
    filters = _normalize_filters(filters)
    return {
        "rows": [],
        "total": 0,
        "page": filters.page,
        "page_size": filters.page_size,
        "pages": 0,
    }
