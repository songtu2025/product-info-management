from dataclasses import dataclass
from io import BytesIO
from math import ceil

from openpyxl import Workbook
from sqlalchemy import text

from app.core.db import get_engine
from app.shared.audit import build_change_set, record_operation_log


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

EXPORT_COLUMNS = (
    ("msku", "MSKU"),
    ("asin", "ASIN"),
    ("store_site", "店铺站点"),
    ("product_name", "产品名称"),
    ("sku", "SKU"),
    ("brand", "品牌"),
    ("listing", "Listing"),
    ("sales_status", "销售状态"),
    ("updated_at", "更新时间"),
)

EDITABLE_FIELDS = (
    "product_name",
    "brand",
    "sales_status",
    "storage_type",
    "category_level_1",
    "category_a",
    "category_b",
    "label_name",
    "msku_shipping_remark",
    "transfer_remark",
    "msku_lock_status",
)

CREATE_FIELDS = (
    "asin",
    "msku",
    "store_site",
    "parent_asin",
    "product_name",
    "sku",
    "brand",
    "fnsku",
    "sales_status",
    "storage_type",
    "category_level_1",
    "category_a",
    "category_b",
    "listing",
    "label_name",
    "msku_shipping_remark",
    "transfer_remark",
    "msku_lock_status",
)


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


def list_products_for_export(filters: ProductFilters) -> list[dict[str, object]]:
    filters = normalize_filters(filters)
    engine = get_engine()
    if engine is None:
        return []

    where_sql, params = _build_where(filters)
    export_sql = text(
        f"""
        SELECT {LIST_COLUMNS}
        FROM amazon_product_info
        {where_sql}
        ORDER BY updated_at DESC, id DESC
        """
    )

    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(export_sql, params).mappings()]


def export_products_to_xlsx(filters: ProductFilters) -> bytes:
    rows = list_products_for_export(filters)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "产品信息"
    sheet.append([header for _, header in EXPORT_COLUMNS])
    for row in rows:
        sheet.append([row.get(field) for field, _ in EXPORT_COLUMNS])

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


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


def get_product_detail(product_id: int) -> dict[str, object] | None:
    engine = get_engine()
    if engine is None:
        return None

    product_sql = text(
        """
        SELECT
            id,
            asin,
            msku,
            store_site,
            parent_asin,
            product_name,
            sku,
            brand,
            fnsku,
            sales_status,
            storage_type,
            category_level_1,
            category_a,
            category_b,
            listing,
            label_name,
            msku_shipping_remark,
            transfer_remark,
            msku_lock_status,
            created_at,
            updated_at
        FROM amazon_product_info
        WHERE id = :product_id
        """
    )
    store_sql = text(
        """
        SELECT store_site, store, country, domain
        FROM amazon_store_site
        WHERE store_site = :store_site
        """
    )
    owner_sql = text(
        """
        SELECT
            owner,
            listing_status,
            listing_maintainer,
            include_inventory_age_assessment,
            project_group
        FROM amazon_listing_owner_config
        WHERE store_site = :store_site AND listing = :listing
        """
    )

    with engine.connect() as conn:
        product = conn.execute(product_sql, {"product_id": product_id}).mappings().first()
        if product is None:
            return None

        store_site = conn.execute(
            store_sql,
            {"store_site": product["store_site"]},
        ).mappings().first()
        owner = None
        if product["listing"]:
            owner = conn.execute(
                owner_sql,
                {"store_site": product["store_site"], "listing": product["listing"]},
            ).mappings().first()

    return {
        "product": dict(product),
        "store_site": dict(store_site) if store_site else None,
        "owner": dict(owner) if owner else None,
    }


def build_update_payload(form_data: dict[str, str]) -> dict[str, str | None]:
    payload: dict[str, str | None] = {}
    for field in EDITABLE_FIELDS:
        if field not in form_data:
            continue
        value = form_data[field].strip()
        payload[field] = value or None
    return payload


def build_create_payload(form_data: dict[str, str]) -> dict[str, str | None]:
    payload: dict[str, str | None] = {}
    for field in CREATE_FIELDS:
        if field not in form_data:
            continue
        value = form_data[field].strip()
        payload[field] = value or None
    return payload


def create_product(
    payload: dict[str, str | None],
    changed_by: str = "system",
) -> int | None:
    store_site = payload.get("store_site")
    msku = payload.get("msku")
    if not store_site or not msku:
        return None

    engine = get_engine()
    if engine is None:
        return None

    allowed_payload = {key: value for key, value in payload.items() if key in CREATE_FIELDS}
    insert_sql = text(
        f"""
        INSERT INTO amazon_product_info (
            {", ".join(allowed_payload)}
        )
        VALUES (
            {", ".join(f":{field}" for field in allowed_payload)}
        )
        """
    )

    with engine.begin() as conn:
        result = conn.execute(insert_sql, allowed_payload)
        product_id = result.lastrowid
        change_data = {
            field: {"old": None, "new": value}
            for field, value in allowed_payload.items()
            if value is not None
        }
        record_operation_log(
            conn,
            table_name="amazon_product_info",
            record_id=product_id,
            operation_type="INSERT",
            change_data=change_data,
            changed_by=changed_by,
        )

    return product_id


def update_product(
    product_id: int,
    payload: dict[str, str | None],
    changed_by: str = "system",
) -> bool:
    if not payload:
        return True

    engine = get_engine()
    if engine is None:
        return False

    allowed_payload = {key: value for key, value in payload.items() if key in EDITABLE_FIELDS}
    if not allowed_payload:
        return True

    select_sql = text(
        f"""
        SELECT {", ".join(EDITABLE_FIELDS)}
        FROM amazon_product_info
        WHERE id = :product_id
        """
    )
    update_sql = text(
        f"""
        UPDATE amazon_product_info
        SET {", ".join(f"{field} = :{field}" for field in allowed_payload)}
        WHERE id = :product_id
        """
    )
    params = {**allowed_payload, "product_id": product_id}

    with engine.begin() as conn:
        before = conn.execute(select_sql, {"product_id": product_id}).mappings().first()
        if before is None:
            return False

        changes = build_change_set(dict(before), allowed_payload)
        result = conn.execute(update_sql, params)
        if result.rowcount > 0:
            record_operation_log(
                conn,
                table_name="amazon_product_info",
                record_id=product_id,
                operation_type="UPDATE",
                change_data=changes,
                changed_by=changed_by,
            )

    return result.rowcount > 0


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
