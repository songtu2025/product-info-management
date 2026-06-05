from dataclasses import dataclass
from io import BytesIO
from math import ceil
from time import monotonic

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
FILTER_OPTIONS_CACHE_TTL_SECONDS = 300
_filter_options_cache: dict[str, object] = {"engine_id": None, "expires_at": 0.0, "value": None}
PRODUCT_LIST_CACHE_TTL_SECONDS = 60
_product_list_cache: dict[tuple[object, ...], dict[str, object]] = {}


@dataclass(frozen=True)
class ProductFilters:
    q: str | None = None
    store_site: str | None = None
    brand: str | None = None
    sales_status: str | None = None
    listing: str | None = None
    listing_owner: str | None = None
    listing_owner_status: str | None = None
    project_group: str | None = None
    page: int = 1
    page_size: int = 20


PRODUCT_ALL_COLUMNS = (
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
    {"key": "listing_owner", "label": "Listing 负责人", "default_visible": True},
    {"key": "listing_owner_status", "label": "Listing 状态", "default_visible": True},
    {"key": "listing_maintainer", "label": "Listing 维护人", "default_visible": False},
    {"key": "include_inventory_age_assessment", "label": "纳入库龄考核", "default_visible": False},
    {"key": "project_group", "label": "项目组", "default_visible": True},
    {"key": "label_name", "label": "标签名", "default_visible": False},
    {"key": "msku_shipping_remark", "label": "MSKU 发货备注", "default_visible": False},
    {"key": "transfer_remark", "label": "借调备注", "default_visible": False},
    {"key": "msku_lock_status", "label": "锁仓 MSKU", "default_visible": False},
    {"key": "created_at", "label": "创建时间", "default_visible": False},
    {"key": "updated_at", "label": "更新时间", "default_visible": True},
)
PRODUCT_LIST_COLUMN_KEYS = {
    "msku",
    "asin",
    "store_site",
    "product_name",
    "sku",
    "brand",
    "sales_status",
    "listing",
    "listing_owner",
    "listing_owner_status",
    "project_group",
    "updated_at",
}
PRODUCT_LIST_COLUMNS = tuple(
    column for column in PRODUCT_ALL_COLUMNS if column["key"] in PRODUCT_LIST_COLUMN_KEYS
)

PRODUCT_PAGE_SIZES = (20, 50, 100, 200)

EXPORT_COLUMNS = (
    ("msku", "MSKU"),
    ("asin", "ASIN"),
    ("store_site", "店铺站点"),
    ("product_name", "产品名称"),
    ("sku", "SKU"),
    ("brand", "品牌"),
    ("listing", "Listing"),
    ("listing_owner", "Listing 负责人"),
    ("listing_owner_status", "Listing 状态"),
    ("listing_maintainer", "Listing 维护人"),
    ("include_inventory_age_assessment", "纳入库龄考核"),
    ("project_group", "项目组"),
    ("sales_status", "销售状态"),
    ("updated_at", "更新时间"),
)

DEFAULT_EXPORT_FIELDS = tuple(field for field, _ in EXPORT_COLUMNS)
EXPORT_COLUMN_MAP = {column["key"]: column["label"] for column in PRODUCT_ALL_COLUMNS}
PRODUCT_TABLE_ALIAS = "p"
PRODUCT_OWNER_JOIN_SQL = """
FROM amazon_product_info p
LEFT JOIN amazon_listing_owner_config lo
  ON p.store_site = lo.store_site
 AND p.listing = lo.listing
"""
PRODUCT_COLUMN_EXPRESSIONS = {
    column["key"]: f"{PRODUCT_TABLE_ALIAS}.{column['key']} AS {column['key']}"
    for column in PRODUCT_ALL_COLUMNS
    if column["key"]
    not in {
        "listing_owner",
        "listing_owner_status",
        "listing_maintainer",
        "include_inventory_age_assessment",
        "project_group",
    }
}
PRODUCT_COLUMN_EXPRESSIONS.update(
    {
        "listing_owner": "lo.owner AS listing_owner",
        "listing_owner_status": "lo.listing_status AS listing_owner_status",
        "listing_maintainer": "lo.listing_maintainer AS listing_maintainer",
        "include_inventory_age_assessment": (
            "lo.include_inventory_age_assessment AS include_inventory_age_assessment"
        ),
        "project_group": "lo.project_group AS project_group",
    }
)
LIST_FIELD_KEYS = ("id", *tuple(column["key"] for column in PRODUCT_LIST_COLUMNS))
LIST_COLUMNS = ",\n    ".join(PRODUCT_COLUMN_EXPRESSIONS[key] for key in LIST_FIELD_KEYS)

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
    page_size = filters.page_size if filters.page_size in PRODUCT_PAGE_SIZES else 20
    return ProductFilters(
        q=_clean(filters.q),
        store_site=_clean(filters.store_site),
        brand=_clean(filters.brand),
        sales_status=_clean(filters.sales_status),
        listing=_clean(filters.listing),
        listing_owner=_clean(filters.listing_owner),
        listing_owner_status=_clean(filters.listing_owner_status),
        project_group=_clean(filters.project_group),
        page=max(filters.page, 1),
        page_size=page_size,
    )


def list_products(filters: ProductFilters) -> dict[str, object]:
    filters = normalize_filters(filters)
    engine = get_engine()
    if engine is None:
        return _empty_page(filters)
    cache_key = _product_list_cache_key(engine, filters)
    cached = _product_list_cache.get(cache_key)
    now = monotonic()
    if cached and now < cached["expires_at"]:
        return cached["value"]

    where_sql, params = _build_where(filters)
    offset = (filters.page - 1) * filters.page_size
    params.update({"limit": filters.page_size, "offset": offset})

    count_sql = text(f"SELECT COUNT(*) {PRODUCT_OWNER_JOIN_SQL} {where_sql}")
    list_sql = text(
        f"""
        SELECT {LIST_COLUMNS}
        {PRODUCT_OWNER_JOIN_SQL}
        {where_sql}
        ORDER BY p.updated_at DESC, p.id DESC
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar_one()
        rows = [dict(row) for row in conn.execute(list_sql, params).mappings()]

    pages = ceil(total / filters.page_size) if total else 0
    page = {
        "rows": rows,
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size,
        "pages": pages,
    }
    _product_list_cache[cache_key] = {
        "expires_at": now + PRODUCT_LIST_CACHE_TTL_SECONDS,
        "value": page,
    }
    return page


def list_products_for_export(
    filters: ProductFilters,
    export_fields: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, object]]:
    filters = normalize_filters(filters)
    engine = get_engine()
    if engine is None:
        return []

    export_columns = resolve_export_columns(export_fields)
    export_select_columns = ",\n    ".join(PRODUCT_COLUMN_EXPRESSIONS[field] for field, _ in export_columns)
    where_sql, params = _build_where(filters)
    export_sql = text(
        f"""
        SELECT {export_select_columns}
        {PRODUCT_OWNER_JOIN_SQL}
        {where_sql}
        ORDER BY p.updated_at DESC, p.id DESC
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
        return {
            "store_sites": [],
            "brands": [],
            "sales_statuses": [],
            "listings": [],
            "listing_owners": [],
            "listing_owner_statuses": [],
            "project_groups": [],
        }
    now = monotonic()
    engine_id = id(engine)
    if (
        _filter_options_cache["engine_id"] == engine_id
        and _filter_options_cache["value"] is not None
        and now < _filter_options_cache["expires_at"]
    ):
        return _filter_options_cache["value"]

    queries = {
        "store_sites": "SELECT DISTINCT store_site FROM amazon_product_info WHERE store_site IS NOT NULL AND store_site <> '' ORDER BY store_site LIMIT 200",
        "brands": "SELECT DISTINCT brand FROM amazon_product_info WHERE brand IS NOT NULL AND brand <> '' ORDER BY brand LIMIT 200",
        "sales_statuses": "SELECT DISTINCT sales_status FROM amazon_product_info WHERE sales_status IS NOT NULL AND sales_status <> '' ORDER BY sales_status LIMIT 100",
        "listings": "SELECT DISTINCT listing FROM amazon_product_info WHERE listing IS NOT NULL AND listing <> '' ORDER BY listing LIMIT 300",
        "listing_owners": "SELECT DISTINCT owner FROM amazon_listing_owner_config WHERE owner IS NOT NULL AND owner <> '' ORDER BY owner LIMIT 300",
        "listing_owner_statuses": "SELECT DISTINCT listing_status FROM amazon_listing_owner_config WHERE listing_status IS NOT NULL AND listing_status <> '' ORDER BY listing_status LIMIT 100",
        "project_groups": "SELECT DISTINCT project_group FROM amazon_listing_owner_config WHERE project_group IS NOT NULL AND project_group <> '' ORDER BY project_group LIMIT 100",
    }

    with engine.connect() as conn:
        options = {
            name: [row[0] for row in conn.execute(text(sql)).all()]
            for name, sql in queries.items()
        }
    _filter_options_cache.update(
        {
            "engine_id": engine_id,
            "expires_at": now + FILTER_OPTIONS_CACHE_TTL_SECONDS,
            "value": options,
        }
    )
    return options


def clear_filter_options_cache() -> None:
    _filter_options_cache.update({"engine_id": None, "expires_at": 0.0, "value": None})


def clear_product_list_cache() -> None:
    _product_list_cache.clear()


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

    clear_filter_options_cache()
    clear_product_list_cache()
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

    if result.rowcount > 0:
        clear_filter_options_cache()
        clear_product_list_cache()
    return result.rowcount > 0


def bulk_update_product_lock_status(
    product_ids: list[int],
    lock_status: str | None,
    changed_by: str = "system",
) -> dict[str, int]:
    clean_ids = list(dict.fromkeys(product_id for product_id in product_ids if product_id > 0))
    if not clean_ids:
        return {"updated": 0, "requested": 0}

    desired_lock_status = LOCKED_MSKU_VALUE if is_locked_msku(lock_status) else None
    engine = get_engine()
    if engine is None:
        return {"updated": 0, "requested": len(clean_ids)}

    id_params = {f"id_{index}": product_id for index, product_id in enumerate(clean_ids)}
    id_placeholders = ", ".join(f":{key}" for key in id_params)
    select_sql = text(
        f"""
        SELECT id, store_site, sku, msku_lock_status
        FROM amazon_product_info
        WHERE id IN ({id_placeholders})
        """
    )
    update_sql = text(
        """
        UPDATE amazon_product_info
        SET msku_lock_status = :msku_lock_status
        WHERE id = :product_id
        """
    )

    updated = 0
    with engine.begin() as conn:
        rows = [dict(row) for row in conn.execute(select_sql, id_params).mappings()]
        if desired_lock_status == LOCKED_MSKU_VALUE:
            _ensure_bulk_lock_has_no_conflict(conn, rows)

        for row in rows:
            changes = build_change_set(row, {"msku_lock_status": desired_lock_status})
            if not changes:
                continue
            result = conn.execute(
                update_sql,
                {
                    "product_id": row["id"],
                    "msku_lock_status": desired_lock_status,
                },
            )
            if result.rowcount > 0:
                updated += 1
                record_operation_log(
                    conn,
                    table_name="amazon_product_info",
                    record_id=row["id"],
                    operation_type="BULK_UPDATE",
                    change_data=changes,
                    changed_by=changed_by,
                )

    if updated:
        clear_filter_options_cache()
        clear_product_list_cache()
    return {"updated": updated, "requested": len(clean_ids)}


def _ensure_bulk_lock_has_no_conflict(conn, rows: list[dict[str, object]]) -> None:
    seen_keys: set[tuple[object, object]] = set()
    for row in rows:
        key = (row.get("store_site"), row.get("sku"))
        if not key[0] or not key[1]:
            continue
        if key in seen_keys:
            raise LockConflictError
        seen_keys.add(key)

    for row in rows:
        if _has_locked_msku_conflict(
            conn,
            store_site=row.get("store_site"),
            sku=row.get("sku"),
            exclude_product_id=int(row["id"]),
        ):
            raise LockConflictError


def _product_list_cache_key(engine, filters: ProductFilters) -> tuple[object, ...]:
    return (
        id(engine),
        filters.q,
        filters.store_site,
        filters.brand,
        filters.sales_status,
        filters.listing,
        filters.listing_owner,
        filters.listing_owner_status,
        filters.project_group,
        filters.page,
        filters.page_size,
    )


def _build_where(filters: ProductFilters) -> tuple[str, dict[str, object]]:
    clauses = []
    params: dict[str, object] = {}

    if filters.q:
        clauses.append(
            """
            (
                p.msku LIKE :q
                OR p.asin LIKE :q
                OR p.sku LIKE :q
                OR p.listing LIKE :q
                OR p.product_name LIKE :q
                OR lo.owner LIKE :q
                OR lo.project_group LIKE :q
            )
            """
        )
        params["q"] = f"%{filters.q}%"

    exact_filters = {
        "p.store_site": ("store_site", filters.store_site),
        "p.brand": ("brand", filters.brand),
        "p.sales_status": ("sales_status", filters.sales_status),
        "p.listing": ("listing", filters.listing),
        "lo.owner": ("listing_owner", filters.listing_owner),
        "lo.listing_status": ("listing_owner_status", filters.listing_owner_status),
        "lo.project_group": ("project_group", filters.project_group),
    }
    for field, (param_name, value) in exact_filters.items():
        if value:
            clauses.append(f"{field} = :{param_name}")
            params[param_name] = value

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
