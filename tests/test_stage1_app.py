from fastapi.testclient import TestClient
from pathlib import Path

from app.core.config import get_settings
from app.main import app


client = TestClient(app)


def test_home_page_renders_admin_shell(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_products",
        lambda filters: {"rows": [], "total": 0, "page": 1, "page_size": 50, "pages": 0},
    )
    monkeypatch.setattr(
        "app.modules.product_info.routes.get_filter_options",
        lambda: {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []},
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "Amazon 运营数据管理后台" in response.text
    assert "产品信息" in response.text
    assert "店铺站点" in response.text
    assert "Listing 负责人" in response.text
    assert 'data-app-content' in response.text
    assert 'data-partial-nav' in response.text
    assert "https://cdn.tailwindcss.com" not in response.text
    assert 'href="http://testserver/static/css/tailwind-lite.css"' in response.text
    assert 'href="http://testserver/static/css/app.css"' in response.text
    assert 'src="http://testserver/static/js/partial-nav.js"' in response.text


def test_tailwind_cdn_is_replaced_by_local_utility_css():
    tailwind_lite = Path("app/static/css/tailwind-lite.css")

    assert tailwind_lite.exists()

    css = tailwind_lite.read_text(encoding="utf-8")
    for selector in [
        ".flex",
        ".grid",
        ".hidden",
        ".min-h-screen",
        ".text-slate-900",
        ".px-5",
        ".py-5",
        ".md\\:grid-cols-3",
        ".lg\\:grid-cols-7",
        ".lg\\:block",
    ]:
        assert selector in css


def test_frontend_behavior_uses_static_javascript_files():
    partial_nav = Path("app/static/js/partial-nav.js")
    product_list = Path("app/static/js/product-list.js")
    partial_nav_js = partial_nav.read_text(encoding="utf-8")

    assert partial_nav.exists()
    assert product_list.exists()
    assert "x-partial-request" in partial_nav_js
    assert "product-list-config" in product_list.read_text(encoding="utf-8")


def test_partial_navigation_guards_downloads_and_stale_responses():
    partial_nav_js = Path("app/static/js/partial-nav.js").read_text(encoding="utf-8")

    assert "content-type" in partial_nav_js
    assert "text/html" in partial_nav_js
    assert "latestRequestId" in partial_nav_js
    assert "requestId !== latestRequestId" in partial_nav_js


def test_frontend_feedback_shows_busy_state_for_navigation_and_forms():
    layout_html = Path("app/templates/layout.html").read_text(encoding="utf-8")
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")
    partial_nav_js = Path("app/static/js/partial-nav.js").read_text(encoding="utf-8")

    assert "data-page-status" in layout_html
    assert 'role="status"' in layout_html
    assert 'aria-live="polite"' in layout_html
    assert ".page-status" in app_css
    assert ".is-busy" in app_css
    assert "setPageBusy" in partial_nav_js
    assert "aria-busy" in partial_nav_js
    assert "event.submitter" in partial_nav_js
    assert "dataset.submitting" in partial_nav_js


def test_frontend_accessibility_keeps_focus_and_disabled_pagination_semantics():
    layout_html = Path("app/templates/layout.html").read_text(encoding="utf-8")
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")
    partial_nav_js = Path("app/static/js/partial-nav.js").read_text(encoding="utf-8")
    product_list_html = Path("app/templates/product_info/list.html").read_text(encoding="utf-8")
    owner_list_html = Path("app/templates/listing_owner/list.html").read_text(encoding="utf-8")

    assert 'data-app-content tabindex="-1"' in layout_html
    assert "content.focus({preventScroll: true})" in partial_nav_js
    assert ":focus-visible" in app_css
    assert "[data-app-content]:focus" in app_css

    for template in [product_list_html, owner_list_html]:
        assert template.count('aria-disabled="true"') >= 4
        assert template.count('tabindex="-1"') >= 4
        assert 'aria-current="page"' in template


def test_partial_navigation_enters_target_page_pending_state_before_fetch():
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")
    partial_nav_js = Path("app/static/js/partial-nav.js").read_text(encoding="utf-8")

    pending_call = "showPendingPage(url, label, pushState, loadingMessage);"
    fetch_call = "const response = await fetch(url"

    assert "showPendingPage" in partial_nav_js
    assert "正在打开" in partial_nav_js
    assert "pending-page" in partial_nav_js
    assert pending_call in partial_nav_js
    assert partial_nav_js.index(pending_call) < partial_nav_js.index(fetch_call)
    assert ".pending-page" in app_css
    assert ".pending-page-title" in app_css
    assert ".pending-page-copy" in app_css


def test_partial_navigation_uses_subtle_transition_animation():
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")
    partial_nav_js = Path("app/static/js/partial-nav.js").read_text(encoding="utf-8")

    assert "showLoadedPage" in partial_nav_js
    assert 'content.classList.add("is-content-entering")' in partial_nav_js
    assert 'content.classList.remove("is-content-entering")' in partial_nav_js
    assert "setTimeout" in partial_nav_js
    assert "pending-page-line" in partial_nav_js

    assert "@keyframes pending-page-enter" in app_css
    assert "@keyframes page-content-enter" in app_css
    assert "[data-app-content].is-content-entering" in app_css
    assert ".pending-page-line" in app_css
    assert "prefers-reduced-motion: reduce" in app_css
    assert "animation: none" in app_css


def test_partial_navigation_leaves_download_routes_to_browser():
    partial_nav_js = Path("app/static/js/partial-nav.js").read_text(encoding="utf-8")

    assert "isDownloadUrl" in partial_nav_js
    assert 'link.hasAttribute("download")' in partial_nav_js
    assert 'link.hasAttribute("data-export-download")' in partial_nav_js
    assert 'url.pathname.startsWith("/products/export")' in partial_nav_js
    assert 'url.pathname === "/products/import/template"' in partial_nav_js
    assert 'url.pathname === "/products/import/issues"' in partial_nav_js
    assert 'url.pathname === "/data-quality/export"' in partial_nav_js
    assert "shouldUsePartial(url, link)" in partial_nav_js


def test_product_list_preferences_show_save_feedback():
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")
    product_list_js = Path("app/static/js/product-list.js").read_text(encoding="utf-8")

    assert "[data-page-status]" in product_list_js
    assert "showPreferenceFeedback" in product_list_js
    assert "savePreference" in product_list_js
    assert "正在保存..." in product_list_js
    assert "已保存。" in product_list_js
    assert "保存失败，请稍后重试。" in product_list_js
    assert "response.ok" in product_list_js
    assert ".page-status-success" in app_css
    assert ".page-status-error" in app_css


def test_product_export_requires_field_confirmation():
    product_list_html = Path("app/templates/product_info/list.html").read_text(encoding="utf-8")
    product_list_js = Path("app/static/js/product-list.js").read_text(encoding="utf-8")
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert "data-export-fields-modal" in product_list_html
    assert "data-export-fields-confirm" in product_list_html
    assert "data-export-fields-cancel" in product_list_html
    assert "openExportFieldsModal" in product_list_js
    assert "closeExportFieldsModal" in product_list_js
    assert "exportFieldsConfirm?.addEventListener" in product_list_js
    assert "正在准备导出..." in product_list_js
    assert ".export-fields-modal" in app_css
    assert ".export-fields-dialog" in app_css


def test_product_list_actions_use_grouped_toolbar_layout():
    product_list_html = Path("app/templates/product_info/list.html").read_text(encoding="utf-8")
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert 'data-list-action-group="export"' in product_list_html
    assert 'data-list-action-group="bulk"' in product_list_html
    assert 'data-list-action-group="manage"' in product_list_html
    assert "data-list-bulk-owner-controls" in product_list_html
    assert ".list-action-group" in app_css
    assert ".list-action-group-bulk" in app_css
    assert ".list-bulk-owner-controls" in app_css


def test_product_list_page_uses_compact_operational_layout():
    product_list_html = Path("app/templates/product_info/list.html").read_text(encoding="utf-8")
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert "product-dashboard-grid" in product_list_html
    assert "product-filter-panel" in product_list_html
    assert "product-filter-grid" in product_list_html
    assert "md:grid-cols-4 lg:grid-cols-7" in product_list_html
    assert "product-filter-view-panel" in product_list_html
    assert "product-results-panel" in product_list_html
    assert "product-results-heading" in product_list_html
    assert "product-results-note" in product_list_html
    assert "product-list-table" in product_list_html
    assert ".product-results-heading" in app_css
    assert ".product-results-note" in app_css
    assert ".product-list-table [data-column=\"actions\"]" in app_css


def test_system_ui_uses_layered_visual_hierarchy():
    layout_html = Path("app/templates/layout.html").read_text(encoding="utf-8")
    product_list_html = Path("app/templates/product_info/list.html").read_text(encoding="utf-8")
    app_css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert "app-header-inner" in layout_html
    assert "app-content" in layout_html
    assert "product-workbench" in product_list_html
    assert "--bg-elevated" in app_css
    assert "--shadow-surface" in app_css
    assert "--shadow-raised" in app_css
    assert ".app-header-inner" in app_css
    assert ".app-content" in app_css
    assert ".product-workbench" in app_css
    assert ".product-results-panel" in app_css
    assert "box-shadow: var(--shadow-raised)" in app_css
    assert ".product-list-table .table-row:hover" in app_css


def test_write_actions_require_confirmation_before_submit():
    product_list_html = Path("app/templates/product_info/list.html").read_text(encoding="utf-8")
    import_upload_html = Path("app/templates/product_import/upload.html").read_text(encoding="utf-8")
    partial_nav_js = Path("app/static/js/partial-nav.js").read_text(encoding="utf-8")
    product_list_js = Path("app/static/js/product-list.js").read_text(encoding="utf-8")

    assert "data-confirm-action" in product_list_html
    assert "data-bulk-confirm" in product_list_html
    assert "data-bulk-action-feedback" in product_list_html
    assert "data-confirm=" in import_upload_html
    assert "写入数据库" in import_upload_html
    assert "confirmSubmit" in partial_nav_js
    assert "window.confirm" in partial_nav_js
    assert 'document.addEventListener("submit", (event) => {\n    if (event.defaultPrevented)' in partial_nav_js
    assert "event.preventDefault()" in partial_nav_js
    assert "updateBulkConfirmMessages" in product_list_js
    assert "showBulkActionFeedback" in product_list_js
    assert "请先选择要操作的产品。" in product_list_js
    assert "selectedCount" in product_list_js
    assert "选中的" in product_list_js


def test_empty_states_offer_clear_next_actions():
    templates = [
        Path("app/templates/product_info/list.html").read_text(encoding="utf-8"),
        Path("app/templates/store_site/list.html").read_text(encoding="utf-8"),
        Path("app/templates/listing_owner/list.html").read_text(encoding="utf-8"),
        Path("app/templates/admin_user/list.html").read_text(encoding="utf-8"),
        Path("app/templates/data_quality/index.html").read_text(encoding="utf-8"),
    ]
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    for template in templates:
        assert "empty-state" in template
        assert "empty-state-title" in template
        assert "empty-state-copy" in template

    assert "empty-state-actions" in templates[0]
    assert "清空筛选" in templates[0]
    assert "新增产品" in templates[0]
    assert "新增店铺站点" in templates[1]
    assert "新增 Listing 负责人" in templates[2]
    assert "新增用户" in templates[3]
    assert "当前无异常" in templates[4]
    assert ".empty-state" in css
    assert ".empty-state-title" in css
    assert ".empty-state-actions" in css


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "amazon-ops-admin"}


def test_db_status_without_database_url_is_explicitly_unconfigured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV_FILE", "__missing_test_env_file__")

    response = client.get("/db/status")

    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert response.json()["reason"] == "DATABASE_URL is not configured"


def test_settings_loads_database_url_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=mysql+pymysql://user:pass@example.com:3306/amazon_ops?charset=utf8mb4\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV_FILE", str(env_file))

    settings = get_settings()

    assert settings.database_url == "mysql+pymysql://user:pass@example.com:3306/amazon_ops?charset=utf8mb4"
