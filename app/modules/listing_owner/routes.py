from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.security import require_admin
from app.core.templates import templates
from app.modules.listing_owner.service import (
    DuplicateListingOwnerError,
    LISTING_OWNER_PAGE_SIZES,
    ListingOwnerFilters,
    build_create_payload,
    build_update_payload,
    create_listing_owner,
    get_filter_options,
    get_listing_owner,
    list_listing_owners,
    update_listing_owner,
)


router = APIRouter(prefix="/listing-owners")


def build_listing_owner_new_context(row: dict[str, object] | None = None, error: str | None = None) -> dict[str, object]:
    return {
        "app_name": get_settings().app_name,
        "active_nav": "Listing 负责人",
        "row": row or {},
        "error": error,
        "options": get_filter_options(),
    }


@router.get("", response_class=HTMLResponse)
def listing_owner_list(
    request: Request,
    q: str | None = None,
    store_site: str | None = None,
    owner: str | None = None,
    listing_status: str | None = None,
    listing_maintainer: str | None = None,
    include_inventory_age_assessment: str | None = None,
    project_group: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    filters = ListingOwnerFilters(
        q=q,
        store_site=store_site,
        owner=owner,
        listing_status=listing_status,
        listing_maintainer=listing_maintainer,
        include_inventory_age_assessment=include_inventory_age_assessment,
        project_group=project_group,
        page=page,
        page_size=page_size,
    )
    owners = _ensure_page(list_listing_owners(filters), filters)
    normalized_filters = ListingOwnerFilters(
        q=filters.q,
        store_site=filters.store_site,
        owner=filters.owner,
        listing_status=filters.listing_status,
        listing_maintainer=filters.listing_maintainer,
        include_inventory_age_assessment=filters.include_inventory_age_assessment,
        project_group=filters.project_group,
        page=int(owners["page"]),
        page_size=int(owners["page_size"]),
    )
    return templates.TemplateResponse(
        request,
        "listing_owner/list.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "Listing 负责人",
            "filters": filters,
            "owners": owners,
            "rows": owners["rows"],
            "options": get_filter_options(),
            "page_sizes": LISTING_OWNER_PAGE_SIZES,
            "pagination": _build_pagination(normalized_filters, int(owners["pages"])),
        },
    )


def _build_pagination(filters: ListingOwnerFilters, pages: int) -> dict[str, object]:
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


def _build_list_url(filters: ListingOwnerFilters, page: int) -> str:
    params = {
        "q": filters.q,
        "store_site": filters.store_site,
        "owner": filters.owner,
        "listing_status": filters.listing_status,
        "listing_maintainer": filters.listing_maintainer,
        "include_inventory_age_assessment": filters.include_inventory_age_assessment,
        "project_group": filters.project_group,
        "page_size": filters.page_size,
        "page": page,
    }
    query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
    return f"?{query}" if query else "?"


def _ensure_page(value: object, filters: ListingOwnerFilters) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    rows = value if isinstance(value, list) else []
    return {
        "rows": rows,
        "total": len(rows),
        "page": filters.page,
        "page_size": filters.page_size,
        "pages": 1 if rows else 0,
    }


@router.get("/new", response_class=HTMLResponse)
def listing_owner_new(request: Request):
    require_admin(request)
    return templates.TemplateResponse(
        request,
        "listing_owner/new.html",
        build_listing_owner_new_context(),
    )


@router.post("/new")
async def listing_owner_create(request: Request):
    user = require_admin(request)
    form = await request.form()
    payload = build_create_payload(dict(form))

    try:
        row_id = create_listing_owner(payload, changed_by=user.username)
    except DuplicateListingOwnerError:
        return templates.TemplateResponse(
            request,
            "listing_owner/new.html",
            build_listing_owner_new_context(payload, "负责人配置已存在，请检查店铺站点和 Listing。"),
            status_code=400,
        )

    if row_id:
        return RedirectResponse("/listing-owners", status_code=303)

    return templates.TemplateResponse(
        request,
        "listing_owner/new.html",
        build_listing_owner_new_context(payload, "保存失败，请至少填写店铺站点和 Listing。"),
        status_code=400,
    )


@router.get("/{row_id}/edit", response_class=HTMLResponse)
def listing_owner_edit(request: Request, row_id: int):
    require_admin(request)
    row = get_listing_owner(row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Listing owner not found")

    return templates.TemplateResponse(
        request,
        "listing_owner/edit.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "Listing 负责人",
            "row": row,
            "error": None,
        },
    )


@router.post("/{row_id}/edit")
async def listing_owner_update(request: Request, row_id: int):
    user = require_admin(request)
    row = get_listing_owner(row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Listing owner not found")

    form = await request.form()
    payload = build_update_payload(dict(form))
    if update_listing_owner(row_id, payload, changed_by=user.username):
        return RedirectResponse("/listing-owners", status_code=303)

    row.update(payload)
    return templates.TemplateResponse(
        request,
        "listing_owner/edit.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "Listing 负责人",
            "row": row,
            "error": "保存失败，请检查数据库连接或负责人配置是否存在。",
        },
        status_code=400,
    )
