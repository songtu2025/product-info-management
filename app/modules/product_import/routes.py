from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.core.config import get_settings
from app.core.security import require_admin
from app.core.templates import templates
from app.modules.product_import.service import (
    build_product_import_template,
    commit_product_import,
    load_import_upload,
    preview_product_import,
    save_import_upload,
)


router = APIRouter()


@router.get("/products/import", response_class=HTMLResponse)
def product_import_page(request: Request):
    require_admin(request)
    return templates.TemplateResponse(
        request,
        "product_import/upload.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "数据导入",
            "preview": None,
            "error": None,
            "import_token": None,
            "commit_result": None,
        },
    )


@router.get("/products/import/template")
def product_import_template():
    content = build_product_import_template()
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="product_import_template.xlsx"'},
    )


@router.post("/products/import/preview", response_class=HTMLResponse)
async def product_import_preview(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    content = await file.read()
    try:
        preview = preview_product_import(content)
        import_token = save_import_upload(content)
        error = None
    except Exception:
        preview = None
        import_token = None
        error = "Excel 解析失败，请确认上传的是标准 .xlsx 文件。"

    return templates.TemplateResponse(
        request,
        "product_import/upload.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "数据导入",
            "preview": preview,
            "error": error,
            "import_token": import_token,
            "commit_result": None,
        },
    )


@router.post("/products/import/commit", response_class=HTMLResponse)
async def product_import_commit(request: Request, import_token: str = Form(...)):
    user = require_admin(request)
    content = load_import_upload(import_token)
    if content is None:
        commit_result = {
            "success": False,
            "updated_count": 0,
            "skipped_count": 0,
            "message": "导入文件已失效，请重新上传。",
        }
    else:
        commit_result = commit_product_import(content, changed_by=user.username)

    return templates.TemplateResponse(
        request,
        "product_import/upload.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "数据导入",
            "preview": commit_result.get("preview"),
            "error": None,
            "import_token": None,
            "commit_result": commit_result,
        },
    )
