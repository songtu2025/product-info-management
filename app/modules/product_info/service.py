from dataclasses import dataclass
from math import ceil

from sqlalchemy import text

from app.core.db import get_engine


@dataclass(frozen=True)
class ProductFilters:
    q: str | None = None
    store_site: str | None = None
    brand: str | None = None
    sales_status: str | None = None
    listing: str | None = None
    page: int = 1
    page_size: int = 50


LIST_COLUMNS = """
    id,
    asin,
    msku,
    store_site,
    product_name,
    sku,
    brand,
    listing,
    sales_status,
    updated_at
"""


def normalize_filters(filters: ProductFilters) -> ProductFilters:
    return ProductFilters(
        q=_clean(filters.q),
        store_site=_clean(filters.store_site),
        brand=_clean(filters.brand),
        sales_status=_clean(filters.sales_status),
        listing=_clean(filters.listing),
        page=max(filters.page, 1),
        page_size=50,
    )


def list_products(filters: ProductFilters) -> dict[str, object]:
    filters = normalize_filters(filters)
    engine = get_engine()
    if engine is None:
        return _empty_page(filters)

    where_sql, params = _build_where(filters)
    offset = (filters.page - 1) * filters.page_size
    params.update({"limit": filters.page_size, "offset": offset})

    count_sql = text(f"SELECT COUNT(*) FROM amazon_product_info {where_sql}")
    list_sql = text(
        f"""
        SELECT {LIST_COLUMNS}
        FROM amazon_product_info
        {where_sql}
        ORDER BY updated_at DESC, id DESC
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar_one()
        rows = [dict(row) for row in conn.execute(list_sql, params).mappings()]

    pages = ceil(total / filters.page_size) if total else 0
    return {
        "rows": rows,
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size,
        "pages": pages,
    }


def get_filter_options() -> dict[str, list[str]]:
    engine = get_engine()
    if engine is None:
        return {"store_sites": [], "brands": [], "sales_statuses": [], "listings": []}

    queries = {
        "store_sites": "SELECT DISTINCT store_site FROM amazon_product_info WHERE store_site IS NOT NULL AND store_site <> '' ORDER BY store_site LIMIT 200",
        "brands": "SELECT DISTINCT brand FROM amazon_product_info WHERE brand IS NOT NULL AND brand <> '' ORDER BY brand LIMIT 200",
        "sales_statuses": "SELECT DISTINCT sales_status FROM amazon_product_info WHERE sales_status IS NOT NULL AND sales_status <> '' ORDER BY sales_status LIMIT 100",
        "listings": "SELECT DISTINCT listing FROM amazon_product_info WHERE listing IS NOT NULL AND listing <> '' ORDER BY listing LIMIT 300",
    }

    with engine.connect() as conn:
        return {
            name: [row[0] for row in conn.execute(text(sql)).all()]
            for name, sql in queries.items()
        }


def _build_where(filters: ProductFilters) -> tuple[str, dict[str, object]]:
    clauses = []
    params: dict[str, object] = {}

    if filters.q:
        clauses.append(
            """
            (
                msku LIKE :q
                OR asin LIKE :q
                OR sku LIKE :q
                OR listing LIKE :q
                OR product_name LIKE :q
            )
            """
        )
        params["q"] = f"%{filters.q}%"

    exact_filters = {
        "store_site": filters.store_site,
        "brand": filters.brand,
        "sales_status": filters.sales_status,
        "listing": filters.listing,
    }
    for field, value in exact_filters.items():
        if value:
            clauses.append(f"{field} = :{field}")
            params[field] = value

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _empty_page(filters: ProductFilters) -> dict[str, object]:
    return {
        "rows": [],
        "total": 0,
        "page": filters.page,
        "page_size": filters.page_size,
        "pages": 0,
    }
