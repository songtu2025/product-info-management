from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.security import require_admin
from app.core.templates import templates
from app.modules.listing_owner.service import (
    build_update_payload,
    get_listing_owner,
    list_listing_owners,
    update_listing_owner,
)


router = APIRouter(prefix="/listing-owners")


@router.get("", response_class=HTMLResponse)
def listing_owner_list(request: Request, q: str | None = None):
    rows = list_listing_owners(q)
    return templates.TemplateResponse(
        request,
        "listing_owner/list.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "Listing 负责人",
            "q": q or "",
            "rows": rows,
        },
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
