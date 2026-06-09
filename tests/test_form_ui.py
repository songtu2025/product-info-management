from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app


client = TestClient(app)


def _product_detail(product_id: int):
    return {
        "product": {
            "id": product_id,
            "msku": "MSKU-001",
            "store_site": "SAYOLA:US",
            "listing": "RB833",
            "product_name": "Product",
            "brand": "BrandA",
            "sales_status": "在售",
            "storage_type": "FBA",
            "category_level_1": "服饰",
            "category_a": "眼镜",
            "category_b": "太阳镜",
            "label_name": "",
            "msku_shipping_remark": "",
            "transfer_remark": "",
            "msku_lock_status": "否",
        },
        "store_site": None,
        "owner": None,
    }


def test_product_forms_use_unified_form_shell(monkeypatch):
    monkeypatch.setattr(
        "app.modules.product_info.routes.list_store_sites",
        lambda: [{"store_site": "SAYOLA:US"}],
    )
    monkeypatch.setattr("app.modules.product_info.routes.get_product_detail", _product_detail)

    for path in ["/products/new", "/products/7/edit"]:
        response = client.get(path)

        assert response.status_code == 200
        assert 'class="form-shell product-form-shell"' in response.text
        assert 'class="form-actions"' in response.text
        assert 'class="btn-secondary"' in response.text
        assert 'class="btn-primary"' in response.text


def test_product_pages_use_layered_product_ui_shells():
    new_template = Path("app/templates/product_info/new.html").read_text(encoding="utf-8")
    edit_template = Path("app/templates/product_info/edit.html").read_text(encoding="utf-8")
    detail_template = Path("app/templates/product_info/detail.html").read_text(encoding="utf-8")
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    for template in [new_template, edit_template]:
        assert 'class="form-shell product-form-shell"' in template
        assert 'class="content-panel product-form-panel"' in template

    assert 'class="product-detail-workbench"' in detail_template
    assert "product-detail-hero" in detail_template
    assert "product-detail-main-grid" in detail_template
    assert "product-detail-section" in detail_template
    assert ".product-form-shell.form-shell" in css
    assert ".product-form-panel.content-panel" in css
    assert ".product-detail-workbench" in css
    assert ".product-detail-section.content-panel" in css


def test_form_error_feedback_uses_unified_alert_structure():
    template_paths = [
        Path("app/templates/product_info/new.html"),
        Path("app/templates/product_info/edit.html"),
        Path("app/templates/store_site/new.html"),
        Path("app/templates/store_site/edit.html"),
        Path("app/templates/listing_owner/new.html"),
        Path("app/templates/listing_owner/edit.html"),
        Path("app/templates/admin_user/new.html"),
        Path("app/templates/admin_user/edit.html"),
        Path("app/templates/admin_user/reset_password.html"),
    ]
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    for template_path in template_paths:
        template = template_path.read_text(encoding="utf-8")
        assert 'class="form-alert"' in template
        assert 'role="alert"' in template
        assert 'aria-live="assertive"' in template
        assert 'class="form-alert-title"' in template
        assert 'class="form-alert-message"' in template

    assert ".form-alert-title" in css
    assert ".form-alert-message" in css
    assert ".read-only-strip" in css
    assert ".required-mark" in css


def test_config_forms_use_unified_form_shell(monkeypatch):
    monkeypatch.setattr(
        "app.modules.store_site.routes.get_store_site",
        lambda store_site_id: {
            "id": store_site_id,
            "store_site": "SAYOLA:US",
            "store": "SAYOLA",
            "country": "US",
            "domain": "amazon.com",
        },
    )
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_filter_options",
        lambda: {
            "store_sites": ["SAYOLA:US"],
            "owners": ["张三"],
            "listing_statuses": ["正常"],
            "listing_maintainers": ["李四"],
            "inventory_age_assessments": ["是"],
            "project_groups": ["项目组A"],
        },
    )
    monkeypatch.setattr(
        "app.modules.listing_owner.routes.get_listing_owner",
        lambda row_id: {
            "id": row_id,
            "store_site": "SAYOLA:US",
            "listing": "RB833",
            "owner": "张三",
            "listing_status": "正常",
            "listing_maintainer": "李四",
            "include_inventory_age_assessment": "是",
            "project_group": "项目组A",
        },
    )

    for path in [
        "/store-sites/new",
        "/store-sites/1/edit",
        "/listing-owners/new",
        "/listing-owners/1/edit",
    ]:
        response = client.get(path)

        assert response.status_code == 200
        assert 'class="form-shell config-form-shell"' in response.text
        assert 'class="content-panel config-form-panel"' in response.text
        assert 'class="form-actions"' in response.text
        assert 'class="btn-secondary"' in response.text
        assert 'class="btn-primary"' in response.text


def test_config_form_templates_use_layered_config_shells():
    template_paths = [
        Path("app/templates/store_site/new.html"),
        Path("app/templates/store_site/edit.html"),
        Path("app/templates/listing_owner/new.html"),
        Path("app/templates/listing_owner/edit.html"),
    ]
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    for template_path in template_paths:
        template = template_path.read_text(encoding="utf-8")
        assert 'class="form-shell config-form-shell"' in template
        assert 'class="content-panel config-form-panel"' in template

    assert ".config-form-shell.form-shell" in css
    assert ".config-form-panel.content-panel" in css


def test_account_templates_use_layered_account_shells():
    form_template_paths = [
        Path("app/templates/auth/password.html"),
        Path("app/templates/admin_user/new.html"),
        Path("app/templates/admin_user/edit.html"),
        Path("app/templates/admin_user/reset_password.html"),
    ]
    login_template = Path("app/templates/auth/login.html").read_text(encoding="utf-8")
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    for template_path in form_template_paths:
        template = template_path.read_text(encoding="utf-8")
        assert 'class="form-shell account-form-shell"' in template
        assert 'class="content-panel account-form-panel"' in template

    assert "account-login-shell" in login_template
    assert "account-login-panel" in login_template
    assert ".account-form-shell.form-shell" in css
    assert ".account-form-panel.content-panel" in css
    assert ".account-login-shell" in css
    assert ".account-login-panel" in css


def test_home_template_uses_layered_home_workbench():
    home_template = Path("app/templates/home.html").read_text(encoding="utf-8")
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert 'class="home-workbench"' in home_template
    assert "home-metric-grid" in home_template
    assert "home-entry-panel" in home_template
    assert "ops-list-table home-placeholder-table" in home_template
    assert ".home-workbench" in css
    assert ".home-entry-panel.content-panel" in css
