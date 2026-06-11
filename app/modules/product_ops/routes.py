from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import get_settings
from app.core.security import require_admin
from app.core.templates import templates
from app.modules.product_import.service import load_import_upload, save_import_upload
from app.modules.product_ops.import_preview import (
    build_forecast_store_site_review,
    build_forecast_store_site_review_workbook,
    build_product_ops_import_preview,
    commit_forecast_store_site_corrections,
    commit_product_ops_source_import,
    commit_sales_allocation_maintenance_import,
    commit_sales_forecast_maintenance_import,
    preview_forecast_store_site_corrections,
    preview_sales_allocation_maintenance_import,
    preview_sales_forecast_maintenance_import,
)
from app.modules.product_ops.service import (
    PRODUCT_OPS_PAGE_SIZES,
    ProductOpsFilters,
    SalesAllocationFilters,
    SalesForecastFilters,
    bulk_update_sales_allocations,
    bulk_update_sales_forecasts,
    export_product_ops_gaps_to_xlsx,
    export_product_ops_rows_to_xlsx,
    export_sales_allocation_maintenance_template,
    export_sales_allocations_to_xlsx,
    export_sales_forecast_maintenance_template,
    export_sales_forecasts_to_xlsx,
    get_listing_profile,
    list_product_ops_gaps,
    list_product_ops_rows,
    list_sales_allocations,
    list_sales_forecasts,
    upsert_sales_forecast,
)
from app.shared.flash import set_flash


router = APIRouter(prefix="/product-ops")


@router.get("", response_class=HTMLResponse)
def product_ops_overview(
    request: Request,
    q: str | None = None,
    store_site: str | None = None,
    listing: str | None = None,
    brand: str | None = None,
    data_status: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    filters = ProductOpsFilters(
        q=q,
        store_site=store_site,
        listing=listing,
        brand=brand,
        data_status=data_status,
        page=page,
        page_size=page_size,
    )
    product_ops = list_product_ops_rows(filters)
    normalized_filters = ProductOpsFilters(
        q=filters.q,
        store_site=filters.store_site,
        listing=filters.listing,
        brand=filters.brand,
        data_status=filters.data_status,
        page=int(product_ops["page"]),
        page_size=int(product_ops["page_size"]),
    )
    return templates.TemplateResponse(
        request,
        "product_ops/overview.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "overview",
            "filters": filters,
            "product_ops": product_ops,
            "rows": product_ops["rows"],
            "page_sizes": PRODUCT_OPS_PAGE_SIZES,
            "pagination": _build_product_ops_pagination(normalized_filters, int(product_ops["pages"])),
            "export_url": _build_query_url(
                "/product-ops/export",
                {
                    "q": filters.q,
                    "store_site": filters.store_site,
                    "listing": filters.listing,
                    "brand": filters.brand,
                    "data_status": filters.data_status,
                },
            ),
        },
    )


@router.get("/export")
def product_ops_overview_export(
    q: str | None = None,
    store_site: str | None = None,
    listing: str | None = None,
    brand: str | None = None,
    data_status: str | None = None,
):
    filters = ProductOpsFilters(
        q=q,
        store_site=store_site,
        listing=listing,
        brand=brand,
        data_status=data_status,
        page=1,
    )
    return _xlsx_response(export_product_ops_rows_to_xlsx(filters), "product_ops_overview.xlsx")


@router.get("/import-preview", response_class=HTMLResponse)
def product_ops_import_preview(request: Request):
    preview = build_product_ops_import_preview()
    return templates.TemplateResponse(
        request,
        "product_ops/import_preview.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "import_preview",
            "preview": preview,
            "datasets": [preview["allocation"], preview["forecast"]],
            "source_commit_result": None,
        },
    )


@router.get("/gaps", response_class=HTMLResponse)
def product_ops_gaps(request: Request):
    gaps = list_product_ops_gaps()
    return templates.TemplateResponse(
        request,
        "product_ops/gaps.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "gaps",
            "gaps": gaps,
            "groups": gaps["groups"],
            "summary": gaps["summary"],
        },
    )


@router.get("/gaps/export")
def product_ops_gaps_export():
    return _xlsx_response(export_product_ops_gaps_to_xlsx(), "product_ops_gaps.xlsx")


@router.get("/listing-profile", response_class=HTMLResponse)
def product_ops_listing_profile(request: Request, store_site: str, listing: str):
    profile = get_listing_profile(store_site, listing)
    return templates.TemplateResponse(
        request,
        "product_ops/listing_profile.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "overview",
            "profile": profile,
            "overview": profile["overview"],
            "issue_labels": profile["issue_labels"],
            "health_summary": profile["health_summary"],
            "health_items": profile["health_items"],
            "purchase_readiness": profile["purchase_readiness"],
            "allocation_rows": profile["allocation_rows"],
            "forecast_rows": profile["forecast_rows"],
        },
    )


@router.post("/import-preview/commit", response_class=HTMLResponse)
def product_ops_import_commit(request: Request):
    user = require_admin(request)
    preview = build_product_ops_import_preview()
    source_commit_result = commit_product_ops_source_import(changed_by=user.username)
    return templates.TemplateResponse(
        request,
        "product_ops/import_preview.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "import_preview",
            "preview": preview,
            "datasets": [preview["allocation"], preview["forecast"]],
            "source_commit_result": source_commit_result,
        },
    )


@router.get("/import-preview/forecast-store-site-review", response_class=HTMLResponse)
def forecast_store_site_review(request: Request):
    review = build_forecast_store_site_review()
    return templates.TemplateResponse(
        request,
        "product_ops/forecast_store_site_review.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "import_preview",
            "review": review,
            "rows": review["rows"],
            "correction_preview": None,
            "commit_result": None,
            "import_token": None,
            "error": None,
        },
    )


@router.post("/import-preview/forecast-store-site-review/preview", response_class=HTMLResponse)
async def forecast_store_site_correction_preview(request: Request, file: UploadFile = File(...)):
    review = build_forecast_store_site_review()
    content = await file.read()
    try:
        correction_preview = preview_forecast_store_site_corrections(content)
        import_token = save_import_upload(content)
        error = None
    except Exception:
        correction_preview = None
        import_token = None
        error = "Excel 解析失败，请确认上传的是修正模板 .xlsx 文件。"

    return templates.TemplateResponse(
        request,
        "product_ops/forecast_store_site_review.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "import_preview",
            "review": review,
            "rows": review["rows"],
            "correction_preview": correction_preview,
            "commit_result": None,
            "import_token": import_token,
            "error": error,
        },
    )


@router.post("/import-preview/forecast-store-site-review/commit", response_class=HTMLResponse)
def forecast_store_site_correction_commit(request: Request, import_token: str = Form(...)):
    user = require_admin(request)
    review = build_forecast_store_site_review()
    content = load_import_upload(import_token)
    if content is None:
        commit_result = {
            "success": False,
            "inserted_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "message": "导入文件已失效，请重新上传。",
            "preview": None,
        }
    else:
        commit_result = commit_forecast_store_site_corrections(content, changed_by=user.username)

    return templates.TemplateResponse(
        request,
        "product_ops/forecast_store_site_review.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "import_preview",
            "review": review,
            "rows": review["rows"],
            "correction_preview": commit_result.get("preview"),
            "commit_result": commit_result,
            "import_token": import_token if not commit_result.get("success") and content is not None else None,
            "error": None,
        },
    )


@router.get("/import-preview/forecast-store-site-review.xlsx")
def forecast_store_site_review_export():
    review = build_forecast_store_site_review()
    return Response(
        build_forecast_store_site_review_workbook(review),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="forecast_store_site_review.xlsx"'},
    )


@router.get("/allocations", response_class=HTMLResponse)
def sales_allocation_list(
    request: Request,
    q: str | None = None,
    store_site: str | None = None,
    listing: str | None = None,
    ratio_status: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    filters = SalesAllocationFilters(
        q=q,
        store_site=store_site,
        listing=listing,
        ratio_status=ratio_status,
        page=page,
        page_size=page_size,
    )
    allocations = list_sales_allocations(filters)
    normalized_filters = SalesAllocationFilters(
        q=filters.q,
        store_site=filters.store_site,
        listing=filters.listing,
        ratio_status=filters.ratio_status,
        page=int(allocations["page"]),
        page_size=int(allocations["page_size"]),
    )
    return templates.TemplateResponse(
        request,
        "product_ops/allocations.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "allocations",
            "filters": filters,
            "allocations": allocations,
            "rows": allocations["rows"],
            "page_sizes": PRODUCT_OPS_PAGE_SIZES,
            "pagination": _build_allocation_pagination(normalized_filters, int(allocations["pages"])),
            "zero_ratio_url": _build_query_url(
                "/product-ops/allocations",
                {
                    "q": filters.q,
                    "store_site": filters.store_site,
                    "listing": filters.listing,
                    "ratio_status": "zero",
                    "page_size": filters.page_size,
                },
            ),
            "missing_allocation_url": _build_query_url(
                "/product-ops",
                {
                    "store_site": filters.store_site,
                    "listing": filters.listing,
                    "data_status": "missing_allocation",
                },
            ),
            "export_url": _build_query_url(
                "/product-ops/allocations/export",
                {
                    "q": filters.q,
                    "store_site": filters.store_site,
                    "listing": filters.listing,
                    "ratio_status": filters.ratio_status,
                },
            ),
            "import_template_url": _build_query_url(
                "/product-ops/allocations/import-template",
                {
                    "q": filters.q,
                    "store_site": filters.store_site,
                    "listing": filters.listing,
                    "ratio_status": filters.ratio_status,
                },
            ),
        },
    )


@router.post("/allocations/bulk-update")
async def sales_allocation_bulk_update(request: Request):
    user = require_admin(request)
    form = await request.form()
    return_url = _allocation_return_url(form)
    row_ids = _parse_int_ids(form.getlist("row_ids"))
    updates, error = _allocation_bulk_update_payload(form)

    if not row_ids:
        set_flash(request, "请先选择要维护的销占比数据。")
        return RedirectResponse(return_url, status_code=303)
    if error:
        set_flash(request, error)
        return RedirectResponse(return_url, status_code=303)
    if not updates:
        set_flash(request, "请填写要维护的字段。")
        return RedirectResponse(return_url, status_code=303)

    result = bulk_update_sales_allocations(row_ids, updates, changed_by=user.username)
    set_flash(request, f"已更新 {result['updated']} 条销占比，跳过 {result['skipped']} 条。")
    return RedirectResponse(return_url, status_code=303)


@router.get("/allocations/export")
def sales_allocation_export(
    q: str | None = None,
    store_site: str | None = None,
    listing: str | None = None,
    ratio_status: str | None = None,
):
    filters = SalesAllocationFilters(q=q, store_site=store_site, listing=listing, ratio_status=ratio_status, page=1)
    return _xlsx_response(export_sales_allocations_to_xlsx(filters), "sales_allocations.xlsx")


@router.get("/allocations/import-template")
def sales_allocation_import_template(
    q: str | None = None,
    store_site: str | None = None,
    listing: str | None = None,
    ratio_status: str | None = None,
):
    filters = SalesAllocationFilters(q=q, store_site=store_site, listing=listing, ratio_status=ratio_status, page=1)
    return _xlsx_response(
        export_sales_allocation_maintenance_template(filters),
        "sales_allocation_maintenance_template.xlsx",
    )


@router.get("/allocations/import", response_class=HTMLResponse)
def sales_allocation_import_page(request: Request):
    return _allocation_import_response(
        request,
        allocation_preview=None,
        commit_result=None,
        import_token=None,
        error=None,
        changed_by=None,
    )


@router.post("/allocations/import/preview", response_class=HTMLResponse)
async def sales_allocation_import_preview(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    try:
        allocation_preview = preview_sales_allocation_maintenance_import(content)
        import_token = save_import_upload(content)
        error = None
    except Exception:
        allocation_preview = None
        import_token = None
        error = "Excel 解析失败，请确认上传的是销占比维护模板 .xlsx 文件。"

    return _allocation_import_response(
        request,
        allocation_preview=allocation_preview,
        commit_result=None,
        import_token=import_token,
        error=error,
        changed_by=None,
    )


@router.post("/allocations/import/commit", response_class=HTMLResponse)
def sales_allocation_import_commit(request: Request, import_token: str = Form(...)):
    user = require_admin(request)
    content = load_import_upload(import_token)
    if content is None:
        commit_result = {
            "success": False,
            "inserted_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "message": "导入文件已失效，请重新上传。",
            "preview": None,
        }
    else:
        commit_result = commit_sales_allocation_maintenance_import(content, changed_by=user.username)

    return _allocation_import_response(
        request,
        allocation_preview=commit_result.get("preview"),
        commit_result=commit_result,
        import_token=import_token if not commit_result.get("success") and content is not None else None,
        error=None,
        changed_by=user.username,
    )


@router.get("/forecasts", response_class=HTMLResponse)
def sales_forecast_list(
    request: Request,
    q: str | None = None,
    store_site: str | None = None,
    site: str | None = None,
    listing: str | None = None,
    forecast_status: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    filters = SalesForecastFilters(
        q=q,
        store_site=store_site,
        site=site,
        listing=listing,
        forecast_status=forecast_status,
        page=page,
        page_size=page_size,
    )
    forecasts = list_sales_forecasts(filters)
    normalized_filters = SalesForecastFilters(
        q=filters.q,
        store_site=filters.store_site,
        site=filters.site,
        listing=filters.listing,
        forecast_status=filters.forecast_status,
        page=int(forecasts["page"]),
        page_size=int(forecasts["page_size"]),
    )
    return templates.TemplateResponse(
        request,
        "product_ops/forecasts.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "forecasts",
            "filters": filters,
            "forecasts": forecasts,
            "rows": forecasts["rows"],
            "page_sizes": PRODUCT_OPS_PAGE_SIZES,
            "pagination": _build_forecast_pagination(normalized_filters, int(forecasts["pages"])),
            "zero_forecast_url": _build_query_url(
                "/product-ops/forecasts",
                {
                    "q": filters.q,
                    "store_site": filters.store_site,
                    "site": filters.site,
                    "listing": filters.listing,
                    "forecast_status": "zero",
                    "page_size": filters.page_size,
                },
            ),
            "missing_forecast_url": _build_query_url(
                "/product-ops",
                {
                    "store_site": filters.store_site,
                    "listing": filters.listing,
                    "data_status": "missing_forecast",
                },
            ),
            "export_url": _build_query_url(
                "/product-ops/forecasts/export",
                {
                    "q": filters.q,
                    "store_site": filters.store_site,
                    "site": filters.site,
                    "listing": filters.listing,
                    "forecast_status": filters.forecast_status,
                },
            ),
            "import_template_url": _build_query_url(
                "/product-ops/forecasts/import-template",
                {
                    "q": filters.q,
                    "store_site": filters.store_site,
                    "site": filters.site,
                    "listing": filters.listing,
                    "forecast_status": filters.forecast_status,
                },
            ),
        },
    )


@router.post("/forecasts/bulk-update")
async def sales_forecast_bulk_update(request: Request):
    user = require_admin(request)
    form = await request.form()
    return_url = _forecast_return_url(form)
    row_ids = _parse_int_ids(form.getlist("row_ids"))
    forecast_units, error = _parse_forecast_units(_form_text(form, "forecast_units"))

    if not row_ids:
        set_flash(request, "请先选择要维护的销售预估。")
        return RedirectResponse(return_url, status_code=303)
    if error:
        set_flash(request, error)
        return RedirectResponse(return_url, status_code=303)

    result = bulk_update_sales_forecasts(row_ids, forecast_units, changed_by=user.username)
    set_flash(request, f"已更新 {result['updated']} 条销售预估，跳过 {result['skipped']} 条。")
    return RedirectResponse(return_url, status_code=303)


@router.post("/forecasts/upsert")
async def sales_forecast_upsert(request: Request):
    user = require_admin(request)
    form = await request.form()
    return_url = _forecast_return_url(form)
    forecast_units, error = _parse_forecast_units(_form_text(form, "forecast_units"))
    if error:
        set_flash(request, error)
        return RedirectResponse(return_url, status_code=303)

    payload = {
        "store_site": _form_text(form, "store_site"),
        "site": _form_text(form, "site"),
        "listing": _form_text(form, "listing"),
        "forecast_month": _form_text(form, "forecast_month"),
        "forecast_units": forecast_units,
    }
    if not payload["store_site"] or not payload["listing"] or not payload["forecast_month"]:
        set_flash(request, "请填写店铺站点、Listing 和月份。")
        return RedirectResponse(return_url, status_code=303)

    result = upsert_sales_forecast(payload, changed_by=user.username)
    action_label = "新增" if result["action"] == "inserted" else "更新" if result["action"] == "updated" else "跳过"
    set_flash(request, f"销售预估已{action_label}。")
    return RedirectResponse(return_url, status_code=303)


@router.get("/forecasts/import-template")
def sales_forecast_import_template(
    q: str | None = None,
    store_site: str | None = None,
    site: str | None = None,
    listing: str | None = None,
    forecast_status: str | None = None,
):
    filters = SalesForecastFilters(
        q=q,
        store_site=store_site,
        site=site,
        listing=listing,
        forecast_status=forecast_status,
        page=1,
    )
    return _xlsx_response(
        export_sales_forecast_maintenance_template(filters),
        "sales_forecast_maintenance_template.xlsx",
    )


@router.get("/forecasts/import", response_class=HTMLResponse)
def sales_forecast_import_page(request: Request):
    return _forecast_import_response(
        request,
        forecast_preview=None,
        commit_result=None,
        import_token=None,
        error=None,
        changed_by=None,
    )


@router.post("/forecasts/import/preview", response_class=HTMLResponse)
async def sales_forecast_import_preview(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    try:
        forecast_preview = preview_sales_forecast_maintenance_import(content)
        import_token = save_import_upload(content)
        error = None
    except Exception:
        forecast_preview = None
        import_token = None
        error = "Excel 解析失败，请确认上传的是销售预估维护模板 .xlsx 文件。"

    return _forecast_import_response(
        request,
        forecast_preview=forecast_preview,
        commit_result=None,
        import_token=import_token,
        error=error,
        changed_by=None,
    )


@router.post("/forecasts/import/commit", response_class=HTMLResponse)
def sales_forecast_import_commit(request: Request, import_token: str = Form(...)):
    user = require_admin(request)
    content = load_import_upload(import_token)
    if content is None:
        commit_result = {
            "success": False,
            "inserted_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "message": "导入文件已失效，请重新上传。",
            "preview": None,
        }
    else:
        commit_result = commit_sales_forecast_maintenance_import(content, changed_by=user.username)

    return _forecast_import_response(
        request,
        forecast_preview=commit_result.get("preview"),
        commit_result=commit_result,
        import_token=import_token if not commit_result.get("success") and content is not None else None,
        error=None,
        changed_by=user.username,
    )


@router.get("/forecasts/export")
def sales_forecast_export(
    q: str | None = None,
    store_site: str | None = None,
    site: str | None = None,
    listing: str | None = None,
    forecast_status: str | None = None,
):
    filters = SalesForecastFilters(
        q=q,
        store_site=store_site,
        site=site,
        listing=listing,
        forecast_status=forecast_status,
        page=1,
    )
    return _xlsx_response(export_sales_forecasts_to_xlsx(filters), "sales_forecasts.xlsx")


def _build_product_ops_pagination(filters: ProductOpsFilters, pages: int) -> dict[str, object]:
    return _build_pagination(
        {
            "q": filters.q,
            "store_site": filters.store_site,
            "listing": filters.listing,
            "brand": filters.brand,
            "data_status": filters.data_status,
            "page_size": filters.page_size,
        },
        filters.page,
        pages,
    )


def _build_allocation_pagination(filters: SalesAllocationFilters, pages: int) -> dict[str, object]:
    return _build_pagination(
        {
            "q": filters.q,
            "store_site": filters.store_site,
            "listing": filters.listing,
            "ratio_status": filters.ratio_status,
            "page_size": filters.page_size,
        },
        filters.page,
        pages,
    )


def _build_forecast_pagination(filters: SalesForecastFilters, pages: int) -> dict[str, object]:
    return _build_pagination(
        {
            "q": filters.q,
            "store_site": filters.store_site,
            "site": filters.site,
            "listing": filters.listing,
            "forecast_status": filters.forecast_status,
            "page_size": filters.page_size,
        },
        filters.page,
        pages,
    )


def _build_pagination(base_params: dict[str, object], current_page: int, pages: int) -> dict[str, object]:
    current_page = max(current_page, 1)
    last_page = max(pages, 1)
    start_page = max(1, current_page - 2)
    end_page = min(last_page, current_page + 2)
    page_numbers = list(range(start_page, end_page + 1))
    return {
        "first_url": _build_url(base_params, 1),
        "prev_url": _build_url(base_params, max(1, current_page - 1)),
        "next_url": _build_url(base_params, min(last_page, current_page + 1)),
        "last_url": _build_url(base_params, last_page),
        "page_numbers": [{"page": page, "url": _build_url(base_params, page)} for page in page_numbers],
    }


def _build_url(base_params: dict[str, object], page: int) -> str:
    params = {**base_params, "page": page}
    query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
    return f"?{query}" if query else "?"


def _build_query_url(path: str, params: dict[str, object]) -> str:
    query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
    return f"{path}?{query}" if query else path


def _allocation_return_url(form) -> str:
    return _build_query_url(
        "/product-ops/allocations",
        {
            "q": _form_text(form, "q"),
            "store_site": _form_text(form, "store_site"),
            "listing": _form_text(form, "listing"),
            "ratio_status": _form_text(form, "ratio_status"),
            "page_size": _form_text(form, "page_size"),
        },
    )


def _allocation_bulk_update_payload(form) -> tuple[dict[str, object], str | None]:
    updates: dict[str, object] = {}
    for field, label in (
        ("style_sales_ratio", "款式销占比"),
        ("sku_sales_ratio", "SKU销占比"),
    ):
        value, error = _parse_optional_ratio(_form_text(form, field), label)
        if error:
            return {}, error
        if value is not None:
            updates[field] = value

    stocking_position = _form_text(form, "stocking_position")
    if stocking_position:
        updates["stocking_position"] = stocking_position
    return updates, None


def _forecast_return_url(form) -> str:
    return _build_query_url(
        "/product-ops/forecasts",
        {
            "q": _form_text(form, "q"),
            "store_site": _form_text(form, "store_site"),
            "site": _form_text(form, "site"),
            "listing": _form_text(form, "listing"),
            "forecast_status": _form_text(form, "forecast_status"),
            "page_size": _form_text(form, "page_size"),
        },
    )


def _parse_forecast_units(value: str) -> tuple[int, str | None]:
    if not value:
        return 0, "请填写月度预估销量。"
    try:
        return int(float(value)), None
    except ValueError:
        return 0, "月度预估销量格式不正确，请填写数字。"


def _parse_optional_ratio(value: str, label: str) -> tuple[float | None, str | None]:
    if not value:
        return None, None
    try:
        if value.endswith("%"):
            return float(value[:-1].strip()) / 100, None
        return float(value), None
    except ValueError:
        return None, f"{label}格式不正确，请填写 35% 或 0.35。"


def _parse_int_ids(values: list[object]) -> list[int]:
    ids: list[int] = []
    for value in values:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return ids


def _form_text(form, key: str) -> str:
    return str(form.get(key) or "").strip()


def _xlsx_response(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _allocation_import_response(
    request: Request,
    allocation_preview: dict[str, object] | None,
    commit_result: dict[str, object] | None,
    import_token: str | None,
    error: str | None,
    changed_by: str | None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "product_ops/sales_allocation_import.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "allocations",
            "allocation_preview": allocation_preview,
            "commit_result": commit_result,
            "import_token": import_token,
            "error": error,
            "changed_by": changed_by,
        },
    )


def _forecast_import_response(
    request: Request,
    forecast_preview: dict[str, object] | None,
    commit_result: dict[str, object] | None,
    import_token: str | None,
    error: str | None,
    changed_by: str | None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "product_ops/sales_forecast_import.html",
        {
            "app_name": get_settings().app_name,
            "active_nav": "产品经营管理",
            "active_tab": "forecasts",
            "forecast_preview": forecast_preview,
            "commit_result": commit_result,
            "import_token": import_token,
            "error": error,
            "changed_by": changed_by,
        },
    )
