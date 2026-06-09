from dataclasses import dataclass
from math import ceil
from time import monotonic

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_engine
from app.shared.audit import build_change_set, record_operation_log
from app.modules.store_site.service import UnknownStoreSiteError, store_site_exists


EDITABLE_FIELDS = (
    "owner",
    "listing_status",
    "listing_maintainer",
    "include_inventory_age_assessment",
    "project_group",
)
CREATE_FIELDS = ("store_site", "listing", *EDITABLE_FIELDS)

LISTING_OWNER_PAGE_SIZES = (50, 100, 200)
FILTER_OPTIONS_CACHE_TTL_SECONDS = 300
_filter_options_cache: dict[str, object] = {"engine_id": None, "expires_at": 0.0, "value": None}
LISTING_OWNER_LIST_CACHE_TTL_SECONDS = 60
_listing_owner_list_cache: dict[tuple[object, ...], dict[str, object]] = {}
PRODUCT_TABLE_AVAILABLE_CACHE_TTL_SECONDS = 300
_product_table_available_cache: dict[str, object] = {
    "engine_id": None,
    "expires_at": 0.0,
    "value": None,
}


class DuplicateListingOwnerError(Exception):
    pass


@dataclass(frozen=True)
class ListingOwnerFilters:
    q: str | None = None
    store_site: str | None = None
    owner: str | None = None
    listing_status: str | None = None
    listing_maintainer: str | None = None
    include_inventory_age_assessment: str | None = None
    project_group: str | None = None
    page: int = 1
    page_size: int = 50


def list_listing_owners(filters: ListingOwnerFilters | str | None = None) -> dict[str, object]:
    filters = normalize_filters(filters)
    engine = get_engine()
    if engine is None:
        return _empty_page(filters)
    cache_key = _listing_owner_list_cache_key(engine, filters)
    cached = _listing_owner_list_cache.get(cache_key)
    now = monotonic()
    if cached and now < cached["expires_at"]:
        return cached["value"]

    where_sql, params = _build_where(filters)
    list_where_sql, _ = _build_where(filters, table_alias="lo")
    offset = (filters.page - 1) * filters.page_size
    params.update({"limit": filters.page_size, "offset": offset})

    has_product_table = _product_table_available(engine)
    product_count_sql = (
        """
            COALESCE(pc.product_count, 0) AS product_count
        """
        if has_product_table
        else "0 AS product_count"
    )
    product_join_sql = (
        """
        LEFT JOIN (
            SELECT store_site, listing, COUNT(*) AS product_count
            FROM amazon_product_info
            WHERE listing IS NOT NULL AND TRIM(listing) <> ''
            GROUP BY store_site, listing
        ) pc
          ON pc.store_site = lo.store_site
         AND pc.listing = lo.listing
        """
        if has_product_table
        else ""
    )

    count_sql = text(f"SELECT COUNT(*) FROM amazon_listing_owner_config {where_sql}")
    list_sql = text(
        f"""
        SELECT
            lo.id,
            lo.store_site,
            lo.listing,
            lo.owner,
            lo.listing_status,
            lo.listing_maintainer,
            lo.include_inventory_age_assessment,
            lo.project_group,
            {product_count_sql},
            lo.updated_at
        FROM amazon_listing_owner_config lo
        {product_join_sql}
        {list_where_sql}
        ORDER BY lo.store_site, lo.listing
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
    _listing_owner_list_cache[cache_key] = {
        "expires_at": now + LISTING_OWNER_LIST_CACHE_TTL_SECONDS,
        "value": page,
    }
    return page


def get_filter_options() -> dict[str, list[str]]:
    engine = get_engine()
    if engine is None:
        return _empty_options()
    now = monotonic()
    engine_id = id(engine)
    if (
        _filter_options_cache["engine_id"] == engine_id
        and _filter_options_cache["value"] is not None
        and now < _filter_options_cache["expires_at"]
    ):
        return _filter_options_cache["value"]

    query = text(
        """
        SELECT option_key, value
        FROM (
            SELECT 'store_sites' AS option_key, value, 1 AS sort_order
            FROM (
                SELECT DISTINCT store_site AS value
                FROM amazon_listing_owner_config
                WHERE store_site IS NOT NULL AND store_site <> ''
                ORDER BY store_site
                LIMIT 300
            ) store_sites
            UNION ALL
            SELECT 'owners' AS option_key, value, 2 AS sort_order
            FROM (
                SELECT DISTINCT owner AS value
                FROM amazon_listing_owner_config
                WHERE owner IS NOT NULL AND owner <> ''
                ORDER BY owner
                LIMIT 300
            ) owners
            UNION ALL
            SELECT 'listing_statuses' AS option_key, value, 3 AS sort_order
            FROM (
                SELECT DISTINCT listing_status AS value
                FROM amazon_listing_owner_config
                WHERE listing_status IS NOT NULL AND listing_status <> ''
                ORDER BY listing_status
                LIMIT 100
            ) listing_statuses
            UNION ALL
            SELECT 'listing_maintainers' AS option_key, value, 4 AS sort_order
            FROM (
                SELECT DISTINCT listing_maintainer AS value
                FROM amazon_listing_owner_config
                WHERE listing_maintainer IS NOT NULL AND listing_maintainer <> ''
                ORDER BY listing_maintainer
                LIMIT 300
            ) listing_maintainers
            UNION ALL
            SELECT 'inventory_age_assessments' AS option_key, value, 5 AS sort_order
            FROM (
                SELECT DISTINCT include_inventory_age_assessment AS value
                FROM amazon_listing_owner_config
                WHERE include_inventory_age_assessment IS NOT NULL
                  AND include_inventory_age_assessment <> ''
                ORDER BY include_inventory_age_assessment
                LIMIT 50
            ) inventory_age_assessments
            UNION ALL
            SELECT 'project_groups' AS option_key, value, 6 AS sort_order
            FROM (
                SELECT DISTINCT project_group AS value
                FROM amazon_listing_owner_config
                WHERE project_group IS NOT NULL AND project_group <> ''
                ORDER BY project_group
                LIMIT 100
            ) project_groups
        ) options
        ORDER BY sort_order, value
        """
    )
    with engine.connect() as conn:
        options = _empty_options()
        for row in conn.execute(query).mappings():
            options[row["option_key"]].append(row["value"])
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


def clear_listing_owner_list_cache() -> None:
    _listing_owner_list_cache.clear()


def clear_product_table_available_cache() -> None:
    _product_table_available_cache.update({"engine_id": None, "expires_at": 0.0, "value": None})


def _product_table_available(engine) -> bool:
    now = monotonic()
    engine_id = id(engine)
    if (
        _product_table_available_cache["engine_id"] == engine_id
        and _product_table_available_cache["value"] is not None
        and now < _product_table_available_cache["expires_at"]
    ):
        return bool(_product_table_available_cache["value"])

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM amazon_product_info LIMIT 1")).first()
        available = True
    except SQLAlchemyError:
        available = False
    _product_table_available_cache.update(
        {
            "engine_id": engine_id,
            "expires_at": now + PRODUCT_TABLE_AVAILABLE_CACHE_TTL_SECONDS,
            "value": available,
        }
    )
    return available


def _build_where(
    filters: ListingOwnerFilters,
    table_alias: str | None = None,
) -> tuple[str, dict[str, object]]:
    def column(field: str) -> str:
        return f"{table_alias}.{field}" if table_alias else field

    clauses: list[str] = []
    params: dict[str, object] = {}
    if filters.q:
        clauses.append(
            f"""
            (
                {column("store_site")} LIKE :q
                OR {column("listing")} LIKE :q
                OR {column("owner")} LIKE :q
                OR {column("listing_status")} LIKE :q
                OR {column("listing_maintainer")} LIKE :q
                OR {column("project_group")} LIKE :q
            )
            """
        )
        params["q"] = f"%{filters.q}%"

    exact_filters = {
        "store_site": filters.store_site,
        "owner": filters.owner,
        "listing_status": filters.listing_status,
        "listing_maintainer": filters.listing_maintainer,
        "include_inventory_age_assessment": filters.include_inventory_age_assessment,
        "project_group": filters.project_group,
    }
    for field, value in exact_filters.items():
        if value:
            clauses.append(f"{column(field)} = :{field}")
            params[field] = value

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def get_listing_owner(row_id: int) -> dict[str, object] | None:
    engine = get_engine()
    if engine is None:
        return None

    sql = text(
        """
        SELECT
            id,
            store_site,
            listing,
            owner,
            listing_status,
            listing_maintainer,
            include_inventory_age_assessment,
            project_group
        FROM amazon_listing_owner_config
        WHERE id = :row_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"row_id": row_id}).mappings().first()
    return dict(row) if row else None


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


def create_listing_owner(
    payload: dict[str, str | None],
    changed_by: str = "system",
) -> int | None:
    store_site = payload.get("store_site")
    listing = payload.get("listing")
    if not store_site or not listing:
        return None

    engine = get_engine()
    if engine is None:
        return None

    allowed_payload = {key: value for key, value in payload.items() if key in CREATE_FIELDS}
    duplicate_sql = text(
        """
        SELECT id
        FROM amazon_listing_owner_config
        WHERE store_site = :store_site AND listing = :listing
        LIMIT 1
        """
    )
    insert_sql = text(
        f"""
        INSERT INTO amazon_listing_owner_config (
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
            {"store_site": store_site, "listing": listing},
        ).first()
        if duplicate:
            raise DuplicateListingOwnerError
        if not store_site_exists(conn, store_site):
            raise UnknownStoreSiteError

        result = conn.execute(insert_sql, allowed_payload)
        row_id = result.lastrowid
        change_data = {
            field: {"old": None, "new": value}
            for field, value in allowed_payload.items()
            if value is not None
        }
        record_operation_log(
            conn,
            table_name="amazon_listing_owner_config",
            record_id=row_id,
            operation_type="INSERT",
            change_data=change_data,
            changed_by=changed_by,
        )

    clear_filter_options_cache()
    clear_listing_owner_list_cache()
    return row_id


def update_listing_owner(
    row_id: int,
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
        FROM amazon_listing_owner_config
        WHERE id = :row_id
        """
    )
    update_sql = text(
        f"""
        UPDATE amazon_listing_owner_config
        SET {", ".join(f"{field} = :{field}" for field in allowed_payload)}
        WHERE id = :row_id
        """
    )
    params = {**allowed_payload, "row_id": row_id}

    with engine.begin() as conn:
        before = conn.execute(select_sql, {"row_id": row_id}).mappings().first()
        if before is None:
            return False

        changes = build_change_set(dict(before), allowed_payload)
        result = conn.execute(update_sql, params)
        if result.rowcount > 0:
            record_operation_log(
                conn,
                table_name="amazon_listing_owner_config",
                record_id=row_id,
                operation_type="UPDATE",
                change_data=changes,
                changed_by=changed_by,
            )

    if result.rowcount > 0:
        clear_filter_options_cache()
        clear_listing_owner_list_cache()
    return result.rowcount > 0


def bulk_assign_listing_owner_from_products(
    product_ids: list[int],
    owner: str,
    changed_by: str = "system",
) -> dict[str, int]:
    clean_ids = list(dict.fromkeys(product_id for product_id in product_ids if product_id > 0))
    owner = owner.strip()
    if not clean_ids or not owner:
        return {"created": 0, "updated": 0, "skipped": len(clean_ids), "requested": len(clean_ids)}

    engine = get_engine()
    if engine is None:
        return {"created": 0, "updated": 0, "skipped": len(clean_ids), "requested": len(clean_ids)}

    id_params = {f"id_{index}": product_id for index, product_id in enumerate(clean_ids)}
    id_placeholders = ", ".join(f":{key}" for key in id_params)
    products_sql = text(
        f"""
        SELECT DISTINCT store_site, listing
        FROM amazon_product_info
        WHERE id IN ({id_placeholders})
        """
    )
    existing_sql = text(
        """
        SELECT id, owner
        FROM amazon_listing_owner_config
        WHERE store_site = :store_site AND listing = :listing
        LIMIT 1
        """
    )
    insert_sql = text(
        """
        INSERT INTO amazon_listing_owner_config (store_site, listing, owner)
        VALUES (:store_site, :listing, :owner)
        """
    )
    update_sql = text(
        """
        UPDATE amazon_listing_owner_config
        SET owner = :owner
        WHERE id = :row_id
        """
    )

    created = 0
    updated = 0
    skipped = 0
    with engine.begin() as conn:
        product_rows = [dict(row) for row in conn.execute(products_sql, id_params).mappings()]
        for row in product_rows:
            store_site = row.get("store_site")
            listing = row.get("listing")
            if not store_site or not listing:
                skipped += 1
                continue

            existing = conn.execute(
                existing_sql,
                {"store_site": store_site, "listing": listing},
            ).mappings().first()
            if existing:
                changes = build_change_set(dict(existing), {"owner": owner})
                if not changes:
                    skipped += 1
                    continue
                result = conn.execute(update_sql, {"row_id": existing["id"], "owner": owner})
                if result.rowcount > 0:
                    updated += 1
                    record_operation_log(
                        conn,
                        table_name="amazon_listing_owner_config",
                        record_id=existing["id"],
                        operation_type="UPDATE",
                        change_data=changes,
                        changed_by=changed_by,
                    )
                continue

            result = conn.execute(
                insert_sql,
                {"store_site": store_site, "listing": listing, "owner": owner},
            )
            row_id = result.lastrowid
            created += 1
            record_operation_log(
                conn,
                table_name="amazon_listing_owner_config",
                record_id=row_id,
                operation_type="INSERT",
                change_data={
                    "store_site": {"old": None, "new": store_site},
                    "listing": {"old": None, "new": listing},
                    "owner": {"old": None, "new": owner},
                },
                changed_by=changed_by,
            )

    if created or updated:
        clear_filter_options_cache()
        clear_listing_owner_list_cache()
    return {"created": created, "updated": updated, "skipped": skipped, "requested": len(clean_ids)}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def normalize_filters(filters: ListingOwnerFilters | str | None) -> ListingOwnerFilters:
    if not isinstance(filters, ListingOwnerFilters):
        filters = ListingOwnerFilters(q=filters)
    page_size = filters.page_size if filters.page_size in LISTING_OWNER_PAGE_SIZES else 50
    return ListingOwnerFilters(
        q=_clean(filters.q),
        store_site=_clean(filters.store_site),
        owner=_clean(filters.owner),
        listing_status=_clean(filters.listing_status),
        listing_maintainer=_clean(filters.listing_maintainer),
        include_inventory_age_assessment=_clean(filters.include_inventory_age_assessment),
        project_group=_clean(filters.project_group),
        page=max(filters.page, 1),
        page_size=page_size,
    )


def _empty_page(filters: ListingOwnerFilters) -> dict[str, object]:
    return {
        "rows": [],
        "total": 0,
        "page": filters.page,
        "page_size": filters.page_size,
        "pages": 0,
    }


def _empty_options() -> dict[str, list[str]]:
    return {
        "store_sites": [],
        "owners": [],
        "listing_statuses": [],
        "listing_maintainers": [],
        "inventory_age_assessments": [],
        "project_groups": [],
    }


def _listing_owner_list_cache_key(engine, filters: ListingOwnerFilters) -> tuple[object, ...]:
    return (
        id(engine),
        filters.q,
        filters.store_site,
        filters.owner,
        filters.listing_status,
        filters.listing_maintainer,
        filters.include_inventory_age_assessment,
        filters.project_group,
        filters.page,
        filters.page_size,
    )
