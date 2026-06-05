from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine, text

from app.modules.product_info import service
from app.modules.product_info.service import (
    LockConflictError,
    ProductFilters,
    create_product,
    _build_where,
    export_products_to_xlsx,
    list_products,
    list_products_for_export,
    normalize_filters,
    update_product,
)


def test_normalize_filters_trims_values_and_forces_page_size():
    filters = normalize_filters(
        ProductFilters(
            q=" abc ",
            store_site=" SAYOLA:US ",
            brand=" ",
            sales_status="在售",
            listing="ListingA",
            page=0,
            page_size=999,
        )
    )

    assert filters.q == "abc"
    assert filters.store_site == "SAYOLA:US"
    assert filters.brand is None
    assert filters.sales_status == "在售"
    assert filters.listing == "ListingA"
    assert filters.page == 1
    assert filters.page_size == 50


def test_build_where_supports_search_and_exact_filters():
    where_sql, params = _build_where(
        ProductFilters(
            q="abc",
            store_site="SAYOLA:US",
            brand="BrandA",
            sales_status="在售",
            listing="ListingA",
        )
    )

    assert "msku LIKE :q" in where_sql
    assert "asin LIKE :q" in where_sql
    assert "product_name LIKE :q" in where_sql
    assert "store_site = :store_site" in where_sql
    assert "brand = :brand" in where_sql
    assert "sales_status = :sales_status" in where_sql
    assert "listing = :listing" in where_sql
    assert params == {
        "q": "%abc%",
        "store_site": "SAYOLA:US",
        "brand": "BrandA",
        "sales_status": "在售",
        "listing": "ListingA",
    }


def test_list_products_returns_all_product_table_fields(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY,
                    asin TEXT,
                    msku TEXT,
                    store_site TEXT,
                    parent_asin TEXT,
                    product_name TEXT,
                    sku TEXT,
                    brand TEXT,
                    fnsku TEXT,
                    sales_status TEXT,
                    storage_type TEXT,
                    category_level_1 TEXT,
                    category_a TEXT,
                    category_b TEXT,
                    listing TEXT,
                    label_name TEXT,
                    msku_shipping_remark TEXT,
                    transfer_remark TEXT,
                    msku_lock_status TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_product_info (
                    id, asin, msku, store_site, parent_asin, product_name, sku, brand,
                    fnsku, sales_status, storage_type, category_level_1, category_a,
                    category_b, listing, label_name, msku_shipping_remark,
                    transfer_remark, msku_lock_status, created_at, updated_at
                )
                VALUES (
                    1, 'B001', 'MSKU-001', 'SAYOLA:US', 'PARENT001', 'Product A',
                    'SKU-001', 'BrandA', 'FNSKU-001', '在售', 'FBA', '服饰',
                    '眼镜', '太阳镜', 'RB833', '标签', '发货备注',
                    '借调备注', '否', '2026-06-01', '2026-06-02'
                )
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    rows = list_products(ProductFilters())["rows"]

    assert rows[0]["parent_asin"] == "PARENT001"
    assert rows[0]["fnsku"] == "FNSKU-001"
    assert rows[0]["label_name"] == "标签"
    assert rows[0]["msku_shipping_remark"] == "发货备注"
    assert rows[0]["created_at"] == "2026-06-01"


def test_list_products_for_export_uses_filters_without_pagination(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY,
                    asin TEXT,
                    msku TEXT,
                    store_site TEXT,
                    product_name TEXT,
                    sku TEXT,
                    brand TEXT,
                    listing TEXT,
                    sales_status TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_product_info (
                    id, asin, msku, store_site, product_name, sku,
                    brand, listing, sales_status, updated_at
                )
                VALUES
                    (1, 'B001', 'MSKU-001', 'SAYOLA:US', 'Product A', 'SKU-001', 'BrandA', 'RB833', '在售', '2026-06-01'),
                    (2, 'B002', 'MSKU-002', 'SAYOLA:US', 'Product B', 'SKU-002', 'BrandB', 'RB831', '在售', '2026-06-01')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    rows = list_products_for_export(ProductFilters(brand="BrandA", page=9))

    assert len(rows) == 1
    assert rows[0]["msku"] == "MSKU-001"
    assert rows[0]["brand"] == "BrandA"


def test_export_products_to_xlsx_uses_selected_safe_fields(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY,
                    msku TEXT,
                    asin TEXT,
                    store_site TEXT,
                    parent_asin TEXT,
                    product_name TEXT,
                    sku TEXT,
                    brand TEXT,
                    fnsku TEXT,
                    sales_status TEXT,
                    storage_type TEXT,
                    category_level_1 TEXT,
                    category_a TEXT,
                    category_b TEXT,
                    listing TEXT,
                    label_name TEXT,
                    msku_shipping_remark TEXT,
                    transfer_remark TEXT,
                    msku_lock_status TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_product_info (
                    id, msku, asin, store_site, product_name, storage_type, updated_at
                )
                VALUES (1, 'MSKU-001', 'B001', 'SAYOLA:US', 'Product 1', 'FBA', '2026-06-04')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    content = export_products_to_xlsx(
        ProductFilters(),
        ["msku", "storage_type", "not_a_column"],
    )
    workbook = load_workbook(BytesIO(content))
    sheet = workbook.active

    assert [cell.value for cell in sheet[1]] == ["MSKU", "仓储类型"]
    assert [cell.value for cell in sheet[2]] == ["MSKU-001", "FBA"]


def test_create_product_rejects_second_locked_msku_for_same_store_site_sku(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    store_site TEXT,
                    msku TEXT,
                    sku TEXT,
                    msku_lock_status TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_product_info (store_site, msku, sku, msku_lock_status)
                VALUES ('SAYOLA:US', 'MSKU-001', 'SKU-001', '锁')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    with pytest.raises(LockConflictError):
        create_product(
            {
                "store_site": "SAYOLA:US",
                "msku": "MSKU-002",
                "sku": "SKU-001",
                "msku_lock_status": "锁",
            }
        )

    with engine.connect() as conn:
        row_count = conn.execute(text("SELECT COUNT(*) FROM amazon_product_info")).scalar_one()

    assert row_count == 1


def test_update_product_rejects_second_locked_msku_for_same_store_site_sku(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY,
                    store_site TEXT,
                    msku TEXT,
                    sku TEXT,
                    product_name TEXT,
                    brand TEXT,
                    sales_status TEXT,
                    storage_type TEXT,
                    category_level_1 TEXT,
                    category_a TEXT,
                    category_b TEXT,
                    label_name TEXT,
                    msku_shipping_remark TEXT,
                    transfer_remark TEXT,
                    msku_lock_status TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_product_info (id, store_site, msku, sku, msku_lock_status)
                VALUES
                    (1, 'SAYOLA:US', 'MSKU-001', 'SKU-001', '锁'),
                    (2, 'SAYOLA:US', 'MSKU-002', 'SKU-001', '否')
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    with pytest.raises(LockConflictError):
        update_product(2, {"msku_lock_status": "锁"})

    with engine.connect() as conn:
        lock_status = conn.execute(
            text("SELECT msku_lock_status FROM amazon_product_info WHERE id = 2")
        ).scalar_one()

    assert lock_status == "否"
