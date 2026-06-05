from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.security import require_admin
from app.core.templates import templates
from app.modules.admin_user.service import (
    create_admin_user,
    get_admin_user,
    list_admin_users,
    reset_admin_user_password,
    update_admin_user,
)
from app.shared.flash import set_flash


router = APIRouter(prefix="/admin-users")


@router.get("", response_class=HTMLResponse)
def admin_user_list(request: Request):
    require_admin(request)
    rows = list_admin_users()
    return templates.TemplateResponse(
        request,
        "admin_user/list.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "用户管理",
            "rows": rows,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def admin_user_new(request: Request):
    require_admin(request)
    return templates.TemplateResponse(
        request,
        "admin_user/new.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "用户管理",
            "row": {"username": "", "role": "viewer", "is_active": 1},
            "error": None,
        },
    )


@router.post("/new")
async def admin_user_create(request: Request):
    user = require_admin(request)
    form = await request.form()
    payload = {
        "username": str(form.get("username") or "").strip(),
        "password": str(form.get("password") or "").strip(),
        "role": str(form.get("role") or "").strip(),
        "is_active": 1 if form.get("is_active") else 0,
    }
    if create_admin_user(payload, changed_by=user.username):
        set_flash(request, "用户已新增。")
        return RedirectResponse("/admin-users", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin_user/new.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "用户管理",
            "row": payload,
            "error": "创建失败，请检查账号是否重复、角色是否正确，或数据库连接是否正常。",
        },
        status_code=400,
    )


@router.get("/{user_id}/edit", response_class=HTMLResponse)
def admin_user_edit(request: Request, user_id: int):
    require_admin(request)
    row = get_admin_user(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Admin user not found")

    return templates.TemplateResponse(
        request,
        "admin_user/edit.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "用户管理",
            "row": row,
            "error": None,
        },
    )


@router.post("/{user_id}/edit")
async def admin_user_update(request: Request, user_id: int):
    user = require_admin(request)
    row = get_admin_user(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Admin user not found")

    form = await request.form()
    payload = {
        "role": str(form.get("role") or "").strip(),
        "is_active": 1 if form.get("is_active") else 0,
    }
    if update_admin_user(user_id, payload, changed_by=user.username):
        set_flash(request, "用户已保存。")
        return RedirectResponse("/admin-users", status_code=303)

    row.update(payload)
    return templates.TemplateResponse(
        request,
        "admin_user/edit.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "用户管理",
            "row": row,
            "error": "保存失败，请检查角色是否正确，或数据库连接是否正常。",
        },
        status_code=400,
    )


@router.get("/{user_id}/reset-password", response_class=HTMLResponse)
def admin_user_reset_password(request: Request, user_id: int):
    require_admin(request)
    row = get_admin_user(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Admin user not found")

    return templates.TemplateResponse(
        request,
        "admin_user/reset_password.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "用户管理",
            "row": row,
            "error": None,
        },
    )


@router.post("/{user_id}/reset-password")
async def admin_user_reset_password_update(request: Request, user_id: int):
    user = require_admin(request)
    row = get_admin_user(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Admin user not found")

    form = await request.form()
    password = str(form.get("password") or "").strip()
    if reset_admin_user_password(user_id, password, changed_by=user.username):
        set_flash(request, "密码已重置。")
        return RedirectResponse("/admin-users", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin_user/reset_password.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "用户管理",
            "row": row,
            "error": "重置失败，请检查新密码是否为空，或数据库连接是否正常。",
        },
        status_code=400,
    )
