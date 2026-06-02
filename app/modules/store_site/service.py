from sqlalchemy import text

from app.core.db import get_engine
from app.shared.audit import build_change_set, record_operation_log


EDITABLE_FIELDS = ("store", "country", "domain")


def list_store_sites(q: str | None = None) -> list[dict[str, object]]:
    engine = get_engine()
    if engine is None:
        return []

    q = _clean(q)
    params: dict[str, object] = {}
    where_sql = ""
    if q:
        where_sql = """
        WHERE store_site LIKE :q
           OR store LIKE :q
           OR country LIKE :q
           OR domain LIKE :q
        """
        params["q"] = f"%{q}%"

    sql = text(
        f"""
        SELECT id, store_site, store, country, domain, updated_at
        FROM amazon_store_site
        {where_sql}
        ORDER BY store_site
        """
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).mappings()]


def get_store_site(store_site_id: int) -> dict[str, object] | None:
    engine = get_engine()
    if engine is None:
        return None

    sql = text(
        """
        SELECT id, store_site, store, country, domain
        FROM amazon_store_site
        WHERE id = :store_site_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"store_site_id": store_site_id}).mappings().first()
    return dict(row) if row else None


def build_update_payload(form_data: dict[str, str]) -> dict[str, str | None]:
    payload: dict[str, str | None] = {}
    for field in EDITABLE_FIELDS:
        if field not in form_data:
            continue
        value = form_data[field].strip()
        payload[field] = value or None
    return payload


def update_store_site(
    store_site_id: int,
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
        FROM amazon_store_site
        WHERE id = :store_site_id
        """
    )
    update_sql = text(
        f"""
        UPDATE amazon_store_site
        SET {", ".join(f"{field} = :{field}" for field in allowed_payload)}
        WHERE id = :store_site_id
        """
    )
    params = {**allowed_payload, "store_site_id": store_site_id}

    with engine.begin() as conn:
        before = conn.execute(select_sql, {"store_site_id": store_site_id}).mappings().first()
        if before is None:
            return False

        changes = build_change_set(dict(before), allowed_payload)
        result = conn.execute(update_sql, params)
        if result.rowcount > 0:
            record_operation_log(
                conn,
                table_name="amazon_store_site",
                record_id=store_site_id,
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
