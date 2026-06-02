import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


def build_change_set(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for field, new_value in after.items():
        old_value = before.get(field)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}
    return changes


def record_operation_log(
    conn: Connection,
    table_name: str,
    record_id: int,
    operation_type: str,
    change_data: dict[str, dict[str, Any]],
    changed_by: str = "system",
) -> None:
    if not change_data:
        return

    conn.execute(
        text(
            """
            INSERT INTO amazon_operation_log (
                table_name,
                record_id,
                operation_type,
                changed_by,
                change_data
            )
            VALUES (
                :table_name,
                :record_id,
                :operation_type,
                :changed_by,
                :change_data
            )
            """
        ),
        {
            "table_name": table_name,
            "record_id": record_id,
            "operation_type": operation_type,
            "changed_by": changed_by,
            "change_data": json.dumps(change_data, ensure_ascii=False, default=str),
        },
    )
