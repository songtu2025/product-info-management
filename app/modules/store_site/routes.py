from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.security import require_admin
from app.core.templates import templates
from app.modules.store_site.service import (
    build_update_payload,
    get_store_site,
    list_store_sites,
    update_store_site,
)


router = APIRouter(prefix="/store-sites")


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
    require_admin(request)
    row = get_store_site(store_site_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Store site not found")

    form = await request.form()
    payload = build_update_payload(dict(form))
    if update_store_site(store_site_id, payload):
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
