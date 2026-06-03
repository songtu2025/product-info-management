from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import get_settings
from app.core.security import require_admin
from app.core.templates import templates
from app.modules.product_info.service import (
    DuplicateProductError,
    ProductFilters,
    PRODUCT_LIST_COLUMNS,
    build_create_payload,
    build_update_payload,
    create_product,
    export_products_to_xlsx,
    get_filter_options,
    get_product_detail,
    list_products,
    update_product,
)
from app.modules.store_site.service import list_store_sites


router = APIRouter()


def build_product_new_context(row: dict[str, object] | None = None, error: str | None = None) -> dict[str, object]:
    return {
        "app_name": get_settings().app_name,
        "active_nav": "产品信息",
        "row": row or {},
        "store_sites": list_store_sites(),
        "error": error,
    }


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
            "product_list_columns": PRODUCT_LIST_COLUMNS,
            "options": options,
            "export_url": "/products/export"
            + (f"?{request.url.query}" if request.url.query else ""),
            "create_url": "/products/new",
        },
    )


@router.get("/products/export")
def product_export(
    q: str | None = None,
    store_site: str | None = None,
    brand: str | None = None,
    sales_status: str | None = None,
    listing: str | None = None,
):
    filters = ProductFilters(
        q=q,
        store_site=store_site,
        brand=brand,
        sales_status=sales_status,
        listing=listing,
        page=1,
    )
    content = export_products_to_xlsx(filters)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="products_export.xlsx"'},
    )


@router.get("/products/new", response_class=HTMLResponse)
def product_new(request: Request):
    require_admin(request)
    return templates.TemplateResponse(
        request,
        "product_info/new.html",
        build_product_new_context(),
    )


@router.post("/products/new")
async def product_create(request: Request):
    user = require_admin(request)
    form = await request.form()
    payload = build_create_payload(dict(form))
    try:
        product_id = create_product(payload, changed_by=user.username)
    except DuplicateProductError:
        return templates.TemplateResponse(
            request,
            "product_info/new.html",
            build_product_new_context(
                payload,
                "该店铺站点下 MSKU 已存在，请检查后再新增。",
            ),
            status_code=400,
        )

    if product_id:
        return RedirectResponse(f"/products/{product_id}", status_code=303)

    return templates.TemplateResponse(
        request,
        "product_info/new.html",
        build_product_new_context(
            payload,
            "保存失败，请至少填写店铺站点和 MSKU，并确认没有重复产品。",
        ),
        status_code=400,
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int):
    detail = get_product_detail(product_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return templates.TemplateResponse(
        request,
        "product_info/detail.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品信息",
            "detail": detail,
        },
    )


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def product_edit(request: Request, product_id: int):
    require_admin(request)
    detail = get_product_detail(product_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return templates.TemplateResponse(
        request,
        "product_info/edit.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品信息",
            "detail": detail,
            "error": None,
        },
    )


@router.post("/products/{product_id}/edit")
async def product_update(request: Request, product_id: int):
    user = require_admin(request)
    detail = get_product_detail(product_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")

    form = await request.form()
    payload = build_update_payload(dict(form))
    if update_product(product_id, payload, changed_by=user.username):
        return RedirectResponse(f"/products/{product_id}", status_code=303)

    detail["product"].update(payload)
    return templates.TemplateResponse(
        request,
        "product_info/edit.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品信息",
            "detail": detail,
            "error": "保存失败，请检查数据库连接或产品是否存在。",
        },
        status_code=400,
    )
