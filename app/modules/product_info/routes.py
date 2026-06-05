from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import get_settings
from app.core.security import current_user, require_admin
from app.core.templates import templates
from app.modules.product_info.service import (
    DuplicateProductError,
    LOCK_CONFLICT_MESSAGE,
    LockConflictError,
    ProductFilters,
    DEFAULT_EXPORT_FIELDS,
    PRODUCT_LIST_COLUMNS,
    PRODUCT_PAGE_SIZES,
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
from app.shared.user_preference import get_user_preference, save_user_preference


router = APIRouter()
COLUMN_PREFERENCE_KEY = "product_info.list.columns"
EXPORT_FIELD_PREFERENCE_KEY = "product_info.export.fields"
EXPORT_FIELD_KEYS = {column["key"] for column in PRODUCT_LIST_COLUMNS}


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
    listing_owner: str | None = None,
    listing_owner_status: str | None = None,
    project_group: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    filters = ProductFilters(
        q=q,
        store_site=store_site,
        brand=brand,
        sales_status=sales_status,
        listing=listing,
        listing_owner=listing_owner,
        listing_owner_status=listing_owner_status,
        project_group=project_group,
        page=page,
        page_size=page_size,
    )
    products = list_products(filters)
    options = get_filter_options()
    normalized_filters = ProductFilters(
        q=filters.q,
        store_site=filters.store_site,
        brand=filters.brand,
        sales_status=filters.sales_status,
        listing=filters.listing,
        listing_owner=filters.listing_owner,
        listing_owner_status=filters.listing_owner_status,
        project_group=filters.project_group,
        page=int(products["page"]),
        page_size=int(products["page_size"]),
    )
    username = _preference_username(request)
    export_field_state = get_user_preference(username, EXPORT_FIELD_PREFERENCE_KEY) if username else {}

    return templates.TemplateResponse(
        request,
        "product_info/list.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品信息",
            "filters": filters,
            "products": products,
            "product_list_columns": PRODUCT_LIST_COLUMNS,
            "default_export_fields": DEFAULT_EXPORT_FIELDS,
            "saved_export_fields": _saved_export_fields(export_field_state),
            "product_page_sizes": PRODUCT_PAGE_SIZES,
            "column_state": get_user_preference(username, COLUMN_PREFERENCE_KEY) if username else {},
            "pagination": _build_pagination(normalized_filters, int(products["pages"])),
            "options": options,
            "export_url": "/products/export"
            + (f"?{request.url.query}" if request.url.query else ""),
            "create_url": "/products/new",
        },
    )


@router.post("/products/preferences/columns")
async def product_column_preference_save(request: Request):
    username = _preference_username(request)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    state = await request.json()
    if not isinstance(state, dict):
        raise HTTPException(status_code=400, detail="Invalid preference")
    if not save_user_preference(username, COLUMN_PREFERENCE_KEY, state):
        raise HTTPException(status_code=500, detail="Save failed")
    return {"ok": True}


@router.post("/products/preferences/export-fields")
async def product_export_field_preference_save(request: Request):
    username = _preference_username(request)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    state = await request.json()
    if not isinstance(state, dict):
        raise HTTPException(status_code=400, detail="Invalid preference")

    fields = state.get("fields")
    if not isinstance(fields, list):
        raise HTTPException(status_code=400, detail="Invalid preference")

    safe_fields = [field for field in fields if isinstance(field, str) and field in EXPORT_FIELD_KEYS]
    if not save_user_preference(username, EXPORT_FIELD_PREFERENCE_KEY, {"fields": safe_fields}):
        raise HTTPException(status_code=500, detail="Save failed")
    return {"ok": True}


@router.get("/products/export")
def product_export(
    q: str | None = None,
    store_site: str | None = None,
    brand: str | None = None,
    sales_status: str | None = None,
    listing: str | None = None,
    listing_owner: str | None = None,
    listing_owner_status: str | None = None,
    project_group: str | None = None,
    export_fields: list[str] | None = Query(None),
):
    filters = ProductFilters(
        q=q,
        store_site=store_site,
        brand=brand,
        sales_status=sales_status,
        listing=listing,
        listing_owner=listing_owner,
        listing_owner_status=listing_owner_status,
        project_group=project_group,
        page=1,
    )
    content = (
        export_products_to_xlsx(filters, export_fields)
        if export_fields
        else export_products_to_xlsx(filters)
    )
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="products_export.xlsx"'},
    )


def _preference_username(request: Request) -> str | None:
    if getattr(request.app.state, "disable_auth", False):
        return "test-admin"
    user = current_user(request)
    return user.username if user else None


def _saved_export_fields(state: dict[str, object] | None) -> list[str]:
    if not state or not isinstance(state.get("fields"), list):
        return list(DEFAULT_EXPORT_FIELDS)
    fields = [field for field in state["fields"] if isinstance(field, str) and field in EXPORT_FIELD_KEYS]
    return fields or list(DEFAULT_EXPORT_FIELDS)


def _build_pagination(filters: ProductFilters, pages: int) -> dict[str, object]:
    current_page = max(filters.page, 1)
    last_page = max(pages, 1)
    start_page = max(1, current_page - 2)
    end_page = min(last_page, current_page + 2)
    page_numbers = list(range(start_page, end_page + 1))
    return {
        "first_url": _build_list_url(filters, 1),
        "prev_url": _build_list_url(filters, max(1, current_page - 1)),
        "next_url": _build_list_url(filters, min(last_page, current_page + 1)),
        "last_url": _build_list_url(filters, last_page),
        "page_numbers": [{"page": page, "url": _build_list_url(filters, page)} for page in page_numbers],
    }


def _build_list_url(filters: ProductFilters, page: int) -> str:
    params = {
        "q": filters.q,
        "store_site": filters.store_site,
        "brand": filters.brand,
        "sales_status": filters.sales_status,
        "listing": filters.listing,
        "listing_owner": filters.listing_owner,
        "listing_owner_status": filters.listing_owner_status,
        "project_group": filters.project_group,
        "page_size": filters.page_size,
        "page": page,
    }
    query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
    return f"?{query}" if query else "?"


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
    except LockConflictError:
        return templates.TemplateResponse(
            request,
            "product_info/new.html",
            build_product_new_context(payload, LOCK_CONFLICT_MESSAGE),
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
    try:
        updated = update_product(product_id, payload, changed_by=user.username)
    except LockConflictError:
        detail["product"].update(payload)
        return templates.TemplateResponse(
            request,
            "product_info/edit.html",
            {
                "app_name": get_settings().app_name,
                "active_nav": "产品信息",
                "detail": detail,
                "error": LOCK_CONFLICT_MESSAGE,
            },
            status_code=400,
        )

    if updated:
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
