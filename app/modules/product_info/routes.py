from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.templates import templates
from app.modules.product_info.service import ProductFilters, get_filter_options, list_products


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def product_list(
    request: Request,
    q: str | None = None,
    store_site: str | None = None,
    brand: str | None = None,
    sales_status: str | None = None,
    listing: str | None = None,
    page: int = 1,
):
    filters = ProductFilters(
        q=q,
        store_site=store_site,
        brand=brand,
        sales_status=sales_status,
        listing=listing,
        page=page,
    )
    products = list_products(filters)
    options = get_filter_options()

    return templates.TemplateResponse(
        request,
        "product_info/list.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品信息",
            "filters": filters,
            "products": products,
            "options": options,
        },
    )
