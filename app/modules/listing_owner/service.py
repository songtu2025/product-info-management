from dataclasses import dataclass
from math import ceil

from sqlalchemy import text

from app.core.db import get_engine
from app.shared.audit import build_change_set, record_operation_log


EDITABLE_FIELDS = (
    "owner",
    "listing_status",
    "listing_maintainer",
    "include_inventory_age_assessment",
    "project_group",
)

LISTING_OWNER_PAGE_SIZES = (50, 100, 200)


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

    where_sql, params = _build_where(filters)
    offset = (filters.page - 1) * filters.page_size
    params.update({"limit": filters.page_size, "offset": offset})

    count_sql = text(f"SELECT COUNT(*) FROM amazon_listing_owner_config {where_sql}")
    list_sql = text(
        f"""
        SELECT
            id,
            store_site,
            listing,
            owner,
            listing_status,
            listing_maintainer,
            include_inventory_age_assessment,
            project_group,
            updated_at
        FROM amazon_listing_owner_config
        {where_sql}
        ORDER BY store_site, listing
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
        return _empty_options()

    queries = {
        "store_sites": "SELECT DISTINCT store_site AS value FROM amazon_listing_owner_config WHERE store_site IS NOT NULL AND store_site <> '' ORDER BY store_site LIMIT 300",
        "owners": "SELECT DISTINCT owner AS value FROM amazon_listing_owner_config WHERE owner IS NOT NULL AND owner <> '' ORDER BY owner LIMIT 300",
        "listing_statuses": "SELECT DISTINCT listing_status AS value FROM amazon_listing_owner_config WHERE listing_status IS NOT NULL AND listing_status <> '' ORDER BY listing_status LIMIT 100",
        "listing_maintainers": "SELECT DISTINCT listing_maintainer AS value FROM amazon_listing_owner_config WHERE listing_maintainer IS NOT NULL AND listing_maintainer <> '' ORDER BY listing_maintainer LIMIT 300",
        "inventory_age_assessments": "SELECT DISTINCT include_inventory_age_assessment AS value FROM amazon_listing_owner_config WHERE include_inventory_age_assessment IS NOT NULL AND include_inventory_age_assessment <> '' ORDER BY include_inventory_age_assessment LIMIT 50",
        "project_groups": "SELECT DISTINCT project_group AS value FROM amazon_listing_owner_config WHERE project_group IS NOT NULL AND project_group <> '' ORDER BY project_group LIMIT 100",
    }
    with engine.connect() as conn:
        return {
            key: [row["value"] for row in conn.execute(text(sql)).mappings()]
            for key, sql in queries.items()
        }


def _build_where(filters: ListingOwnerFilters) -> tuple[str, dict[str, object]]:
    clauses: list[str] = []
    params: dict[str, object] = {}
    if filters.q:
        clauses.append(
            """
            (
                store_site LIKE :q
                OR listing LIKE :q
                OR owner LIKE :q
                OR listing_status LIKE :q
                OR listing_maintainer LIKE :q
                OR project_group LIKE :q
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
            clauses.append(f"{field} = :{field}")
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

    return result.rowcount > 0


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
