from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.templates import templates
from app.modules.operation_log.service import OperationLogFilters, list_operation_logs


router = APIRouter(prefix="/operation-logs")


@router.get("", response_class=HTMLResponse)
def operation_log_list(
    request: Request,
    table_name: str | None = None,
    record_id: str | None = None,
    operation_type: str | None = None,
):
    filters = OperationLogFilters(
        table_name=table_name,
        record_id=_parse_record_id(record_id),
        operation_type=operation_type,
    )
    rows = list_operation_logs(filters)
    return templates.TemplateResponse(
        request,
        "operation_log/list.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "操作日志",
            "filters": filters,
            "record_id_value": record_id or "",
            "rows": rows,
        },
    )


def _parse_record_id(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.isdigit():
        return None
    return int(value)
