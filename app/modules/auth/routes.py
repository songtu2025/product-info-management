from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.security import authenticate_user, change_user_password, current_user
from app.core.templates import templates
from app.shared.flash import set_flash


router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "app_name": get_settings().app_name,
            "next": next or "/",
            "error": None,
        },
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    user = authenticate_user(username.strip(), password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "app_name": get_settings().app_name,
                "next": next or "/",
                "error": "账号或密码错误。",
            },
            status_code=400,
        )

    request.session["user"] = {"username": user.username, "role": user.role}
    return RedirectResponse(next or "/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/account/password", response_class=HTMLResponse)
def password_page(request: Request):
    user = current_user(request)
    return templates.TemplateResponse(
        request,
        "auth/password.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "账号设置",
            "username": user.username if user else "",
            "error": None,
        },
    )


@router.post("/account/password", response_class=HTMLResponse)
def password_update(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    user = current_user(request)
    username = user.username if user else ""
    error = None
    if new_password != confirm_password:
        error = "两次输入的新密码不一致。"
    elif not change_user_password(username, current_password, new_password):
        error = "原密码不正确，或新密码为空。"

    if error:
        return templates.TemplateResponse(
            request,
            "auth/password.html",
            {
                "app_name": get_settings().app_name,
                "active_nav": "账号设置",
                "username": username,
                "error": error,
            },
            status_code=400,
        )

    set_flash(request, "密码已修改。")
    return RedirectResponse("/account/password", status_code=303)
