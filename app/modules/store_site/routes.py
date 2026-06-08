from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.security import require_admin
from app.core.templates import templates
from app.modules.store_site.service import (
    DuplicateStoreSiteError,
    build_create_payload,
    build_update_payload,
    create_store_site,
    get_store_site,
    list_store_sites,
    update_store_site,
)
from app.shared.flash import set_flash


router = APIRouter(prefix="/store-sites")


def build_store_site_new_context(row: dict[str, object] | None = None, error: str | None = None) -> dict[str, object]:
    domain_by_country = {
        site["country"]: site["domain"]
        for site in list_store_sites()
        if site.get("country") and site.get("domain")
    }
    return {
        "app_name": get_settings().app_name,
        "active_nav": "店铺站点",
        "row": row or {},
        "error": error,
        "domain_by_country": domain_by_country,
    }


@router.get("", response_class=HTMLResponse)
def store_site_list(request: Request, q: str | None = None):
    rows = list_store_sites(q)
    return templates.TemplateResponse(
        request,
        "store_site/list.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "店铺站点",
            "q": q or "",
            "rows": rows,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def store_site_new(request: Request, store_site: str | None = None):
    require_admin(request)
    row = {"store_site": store_site} if store_site else None
    return templates.TemplateResponse(
        request,
        "store_site/new.html",
        build_store_site_new_context(row),
    )


@router.post("/new")
async def store_site_create(request: Request):
    user = require_admin(request)
    form = await request.form()
    payload = build_create_payload(dict(form))

    try:
        store_site_id = create_store_site(payload, changed_by=user.username)
    except DuplicateStoreSiteError:
        return templates.TemplateResponse(
            request,
            "store_site/new.html",
            build_store_site_new_context(payload, "店铺站点已存在，请检查后再新增。"),
            status_code=400,
        )

    if store_site_id:
        set_flash(request, "店铺站点已新增。")
        return RedirectResponse("/store-sites", status_code=303)

    return templates.TemplateResponse(
        request,
        "store_site/new.html",
        build_store_site_new_context(payload, "保存失败，请至少填写店铺站点。"),
        status_code=400,
    )


@router.get("/{store_site_id}/edit", response_class=HTMLResponse)
def store_site_edit(request: Request, store_site_id: int):
    require_admin(request)
    row = get_store_site(store_site_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Store site not found")

    return templates.TemplateResponse(
        request,
        "store_site/edit.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "店铺站点",
            "row": row,
            "error": None,
        },
    )


@router.post("/{store_site_id}/edit")
async def store_site_update(request: Request, store_site_id: int):
    user = require_admin(request)
    row = get_store_site(store_site_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Store site not found")

    form = await request.form()
    payload = build_update_payload(dict(form))
    if update_store_site(store_site_id, payload, changed_by=user.username):
        set_flash(request, "店铺站点已保存。")
        return RedirectResponse("/store-sites", status_code=303)

    row.update(payload)
    return templates.TemplateResponse(
        request,
        "store_site/edit.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "店铺站点",
            "row": row,
            "error": "保存失败，请检查数据库连接或店铺站点是否存在。",
        },
        status_code=400,
    )
