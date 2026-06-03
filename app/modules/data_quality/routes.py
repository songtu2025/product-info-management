from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.templates import templates
from app.modules.data_quality.service import get_product_quality_report


router = APIRouter(prefix="/data-quality")


@router.get("", response_class=HTMLResponse)
def data_quality_page(request: Request):
    report = get_product_quality_report()
    return templates.TemplateResponse(
        request,
        "data_quality/index.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "数据质量",
            "report": report,
        },
    )
