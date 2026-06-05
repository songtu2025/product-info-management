from time import monotonic

from sqlalchemy import text

from app.core.db import get_engine
from app.shared.audit import build_change_set, record_operation_log


EDITABLE_FIELDS = ("store", "country", "domain")
CREATE_FIELDS = ("store_site", "store", "country", "domain")
STORE_SITE_LIST_CACHE_TTL_SECONDS = 300
_store_site_list_cache: dict[str, object] = {"engine_id": None, "expires_at": 0.0, "value": None}


class DuplicateStoreSiteError(Exception):
    pass


def list_store_sites(q: str | None = None) -> list[dict[str, object]]:
    engine = get_engine()
    if engine is None:
        return []

    q = _clean(q)
    now = monotonic()
    engine_id = id(engine)
    if (
        q is None
        and _store_site_list_cache["engine_id"] == engine_id
        and _store_site_list_cache["value"] is not None
        and now < _store_site_list_cache["expires_at"]
    ):
        return _store_site_list_cache["value"]

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
        rows = [dict(row) for row in conn.execute(sql, params).mappings()]
    if q is None:
        _store_site_list_cache.update(
            {
                "engine_id": engine_id,
                "expires_at": now + STORE_SITE_LIST_CACHE_TTL_SECONDS,
                "value": rows,
            }
        )
    return rows


def clear_store_site_list_cache() -> None:
    _store_site_list_cache.update({"engine_id": None, "expires_at": 0.0, "value": None})


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


def build_create_payload(form_data: dict[str, str]) -> dict[str, str | None]:
    payload: dict[str, str | None] = {}
    for field in CREATE_FIELDS:
        if field not in form_data:
            continue
        value = form_data[field].strip()
        payload[field] = value or None
    return payload


def create_store_site(
    payload: dict[str, str | None],
    changed_by: str = "system",
) -> int | None:
    store_site = payload.get("store_site")
    if not store_site:
        return None

    engine = get_engine()
    if engine is None:
        return None

    allowed_payload = {key: value for key, value in payload.items() if key in CREATE_FIELDS}
    duplicate_sql = text(
        """
        SELECT id
        FROM amazon_store_site
        WHERE store_site = :store_site
        LIMIT 1
        """
    )
    insert_sql = text(
        f"""
        INSERT INTO amazon_store_site (
            {", ".join(allowed_payload)}
        )
        VALUES (
            {", ".join(f":{field}" for field in allowed_payload)}
        )
        """
    )

    with engine.begin() as conn:
        duplicate = conn.execute(duplicate_sql, {"store_site": store_site}).first()
        if duplicate:
            raise DuplicateStoreSiteError

        result = conn.execute(insert_sql, allowed_payload)
        store_site_id = result.lastrowid
        change_data = {
            field: {"old": None, "new": value}
            for field, value in allowed_payload.items()
            if value is not None
        }
        record_operation_log(
            conn,
            table_name="amazon_store_site",
            record_id=store_site_id,
            operation_type="INSERT",
            change_data=change_data,
            changed_by=changed_by,
        )

    clear_store_site_list_cache()
    return store_site_id


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

    if result.rowcount > 0:
        clear_store_site_list_cache()
    return result.rowcount > 0


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
