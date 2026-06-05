from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.templates import templates
from app.modules.operation_log.service import OperationLogFilters, get_operation_log_page


router = APIRouter(prefix="/operation-logs")


@router.get("", response_class=HTMLResponse)
def operation_log_list(
    request: Request,
    table_name: str | None = None,
    record_id: str | None = None,
    operation_type: str | None = None,
    changed_by: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    filters = OperationLogFilters(
        table_name=table_name,
        record_id=_parse_record_id(record_id),
        operation_type=operation_type,
        changed_by=changed_by,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    log_page = get_operation_log_page(filters)
    return templates.TemplateResponse(
        request,
        "operation_log/list.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "操作日志",
            "filters": filters,
            "record_id_value": record_id or "",
            "rows": log_page["rows"],
            "log_page": log_page,
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
