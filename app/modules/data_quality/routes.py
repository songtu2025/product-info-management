from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app.core.config import get_settings
from app.core.templates import templates
from app.modules.data_quality.service import build_quality_issue_workbook, get_product_quality_report


router = APIRouter(prefix="/data-quality")


@router.get("", response_class=HTMLResponse)
def data_quality_page(request: Request, store_site: str | None = None):
    report = (
        get_product_quality_report(store_site=store_site)
        if store_site
        else get_product_quality_report()
    )
    return templates.TemplateResponse(
        request,
        "data_quality/index.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "数据质量",
            "report": report,
            "store_site": store_site,
        },
    )


@router.get("/export")
def data_quality_export(store_site: str | None = None):
    report = (
        get_product_quality_report(store_site=store_site)
        if store_site
        else get_product_quality_report()
    )
    content = build_quality_issue_workbook(report)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="data_quality_issues.xlsx"'},
    )
