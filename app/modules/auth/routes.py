from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.security import authenticate_user
from app.core.templates import templates


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
