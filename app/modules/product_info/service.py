from dataclasses import dataclass
from io import BytesIO
from math import ceil

from openpyxl import Workbook
from sqlalchemy import text

from app.core.db import get_engine
from app.shared.audit import build_change_set, record_operation_log


class DuplicateProductError(Exception):
    pass


class LockConflictError(Exception):
    pass


LOCKED_MSKU_VALUE = "锁"
LOCK_CONFLICT_MESSAGE = "同一店铺站点 + SKU 下最多只能有一个锁仓 MSKU 为“锁”。"


@dataclass(frozen=True)
class ProductFilters:
    q: str | None = None
    store_site: str | None = None
    brand: str | None = None
    sales_status: str | None = None
    listing: str | None = None
    page: int = 1
    page_size: int = 50


PRODUCT_LIST_COLUMNS = (
    {"key": "id", "label": "ID", "default_visible": False},
    {"key": "msku", "label": "MSKU", "default_visible": True},
    {"key": "asin", "label": "ASIN", "default_visible": True},
    {"key": "store_site", "label": "店铺站点", "default_visible": True},
    {"key": "parent_asin", "label": "父 ASIN", "default_visible": False},
    {"key": "product_name", "label": "产品名称", "default_visible": True},
    {"key": "sku", "label": "SKU", "default_visible": True},
    {"key": "brand", "label": "品牌", "default_visible": True},
    {"key": "fnsku", "label": "FNSKU", "default_visible": False},
    {"key": "sales_status", "label": "销售状态", "default_visible": True},
    {"key": "storage_type", "label": "仓储类型", "default_visible": False},
    {"key": "category_level_1", "label": "一级品类", "default_visible": False},
    {"key": "category_a", "label": "品类 A", "default_visible": False},
    {"key": "category_b", "label": "品类 B", "default_visible": False},
    {"key": "listing", "label": "Listing", "default_visible": True},
    {"key": "label_name", "label": "标签名", "default_visible": False},
    {"key": "msku_shipping_remark", "label": "MSKU 发货备注", "default_visible": False},
    {"key": "transfer_remark", "label": "借调备注", "default_visible": False},
    {"key": "msku_lock_status", "label": "锁仓 MSKU", "default_visible": False},
    {"key": "created_at", "label": "创建时间", "default_visible": False},
    {"key": "updated_at", "label": "更新时间", "default_visible": True},
)

PRODUCT_PAGE_SIZES = (50, 100, 200)

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

DEFAULT_EXPORT_FIELDS = tuple(field for field, _ in EXPORT_COLUMNS)
EXPORT_COLUMN_MAP = {column["key"]: column["label"] for column in PRODUCT_LIST_COLUMNS}
LIST_COLUMNS = ",\n    ".join(column["key"] for column in PRODUCT_LIST_COLUMNS)

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
    page_size = filters.page_size if filters.page_size in PRODUCT_PAGE_SIZES else 50
    return ProductFilters(
        q=_clean(filters.q),
        store_site=_clean(filters.store_site),
        brand=_clean(filters.brand),
        sales_status=_clean(filters.sales_status),
        listing=_clean(filters.listing),
        page=max(filters.page, 1),
        page_size=page_size,
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


def list_products_for_export(
    filters: ProductFilters,
    export_fields: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, object]]:
    filters = normalize_filters(filters)
    engine = get_engine()
    if engine is None:
        return []

    export_columns = resolve_export_columns(export_fields)
    export_select_columns = ",\n    ".join(field for field, _ in export_columns)
    where_sql, params = _build_where(filters)
    export_sql = text(
        f"""
        SELECT {export_select_columns}
        FROM amazon_product_info
        {where_sql}
        ORDER BY updated_at DESC, id DESC
        """
    )

    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(export_sql, params).mappings()]


def export_products_to_xlsx(
    filters: ProductFilters,
    export_fields: list[str] | tuple[str, ...] | None = None,
) -> bytes:
    export_columns = resolve_export_columns(export_fields)
    rows = list_products_for_export(filters, export_fields)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "产品信息"
    sheet.append([header for _, header in export_columns])
    for row in rows:
        sheet.append([row.get(field) for field, _ in export_columns])

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def resolve_export_columns(export_fields: list[str] | tuple[str, ...] | None = None) -> tuple[tuple[str, str], ...]:
    selected_fields = export_fields or DEFAULT_EXPORT_FIELDS
    columns = tuple(
        (field, EXPORT_COLUMN_MAP[field])
        for field in selected_fields
        if field in EXPORT_COLUMN_MAP
    )
    if columns:
        return columns
    return EXPORT_COLUMNS


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
    duplicate_sql = text(
        """
        SELECT id
        FROM amazon_product_info
        WHERE store_site = :store_site AND msku = :msku
        LIMIT 1
        """
    )
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
        duplicate = conn.execute(
            duplicate_sql,
            {"store_site": store_site, "msku": msku},
        ).first()
        if duplicate:
            raise DuplicateProductError
        if is_locked_msku(allowed_payload.get("msku_lock_status")) and _has_locked_msku_conflict(
            conn,
            store_site=store_site,
            sku=allowed_payload.get("sku"),
        ):
            raise LockConflictError

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
        SELECT store_site, sku, {", ".join(EDITABLE_FIELDS)}
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
        desired_lock_status = allowed_payload.get("msku_lock_status", before["msku_lock_status"])
        if is_locked_msku(desired_lock_status) and _has_locked_msku_conflict(
            conn,
            store_site=before["store_site"],
            sku=before["sku"],
            exclude_product_id=product_id,
        ):
            raise LockConflictError

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


def is_locked_msku(value: object) -> bool:
    return value == LOCKED_MSKU_VALUE


def _has_locked_msku_conflict(
    conn,
    store_site: object,
    sku: object,
    exclude_product_id: int | None = None,
) -> bool:
    if not store_site or not sku:
        return False

    params = {
        "store_site": store_site,
        "sku": sku,
        "lock_status": LOCKED_MSKU_VALUE,
    }
    exclude_sql = ""
    if exclude_product_id is not None:
        exclude_sql = "AND id <> :exclude_product_id"
        params["exclude_product_id"] = exclude_product_id

    query = text(
        f"""
        SELECT id
        FROM amazon_product_info
        WHERE store_site = :store_site
          AND sku = :sku
          AND msku_lock_status = :lock_status
          {exclude_sql}
        LIMIT 1
        """
    )
    return conn.execute(query, params).first() is not None


def _empty_page(filters: ProductFilters) -> dict[str, object]:
    return {
        "rows": [],
        "total": 0,
        "page": filters.page,
        "page_size": filters.page_size,
        "pages": 0,
    }
