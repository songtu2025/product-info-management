from sqlalchemy import create_engine, text

from app.modules.product_info import service
from app.modules.product_info.service import (
    ProductFilters,
    _build_where,
    list_products_for_export,
    normalize_filters,
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
