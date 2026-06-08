from time import monotonic

from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_engine


QUALITY_REPORT_CACHE_TTL_SECONDS = 60
_quality_report_cache: dict[str, object] = {"engine_id": None, "expires_at": 0.0, "value": None}
QUALITY_RULES = (
    ("missing_asin", "缺 ASIN", "asin"),
    ("missing_listing", "缺 Listing", "listing"),
    ("missing_brand", "缺品牌", "brand"),
    ("missing_sales_status", "缺销售状态", "sales_status"),
    ("missing_product_name", "缺产品名称", "product_name"),
)
RELATION_RULES = (
    ("missing_listing_owner_config", "缺 Listing 负责人配置"),
    ("orphan_listing_owner_config", "无产品使用的负责人配置"),
    ("unknown_product_store_site", "产品引用未知店铺站点"),
    ("unknown_listing_owner_store_site", "负责人配置引用未知店铺站点"),
)


def get_product_quality_report(store_site: str | None = None) -> dict[str, object]:
    store_site = _normalize_store_site(store_site)
    engine = get_engine()
    if engine is None:
        return _build_report(0, _empty_field_issues(), _empty_relation_issues())
    now = monotonic()
    engine_id = id(engine)
    if store_site is None and (
        _quality_report_cache["engine_id"] == engine_id
        and _quality_report_cache["value"] is not None
        and now < _quality_report_cache["expires_at"]
    ):
        return _quality_report_cache["value"]

    store_site_params = _store_site_params(store_site)
    product_store_site_filter = _store_site_filter("p", store_site)
    total_sql = text(
        f"""
        SELECT COUNT(*)
        FROM amazon_product_info p
        WHERE 1 = 1
        {product_store_site_filter}
        """
    )

    with engine.connect() as conn:
        total = conn.execute(total_sql, store_site_params).scalar_one()
        field_issues = []
        for key, label, field in QUALITY_RULES:
            where_sql = f"(p.{field} IS NULL OR TRIM(p.{field}) = '')"
            count = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM amazon_product_info p
                    WHERE {where_sql}
                    {product_store_site_filter}
                    """
                ),
                store_site_params,
            ).scalar_one()
            rows = [
                dict(row)
                for row in conn.execute(
                    text(
                        f"""
                        SELECT p.id, p.store_site, p.msku, p.product_name
                        FROM amazon_product_info p
                        WHERE {where_sql}
                        {product_store_site_filter}
                        ORDER BY updated_at DESC, id DESC
                        LIMIT 20
                        """
                    ),
                    store_site_params,
                ).mappings()
            ]
            field_issues.append(
                {
                    "key": key,
                    "label": label,
                    "field": field,
                    "count": count,
                    "rows": rows,
                }
            )
        relation_issues = _get_relation_issues(conn, store_site)

    report = _build_report(total, field_issues, relation_issues)
    if store_site is None:
        _quality_report_cache.update(
            {
                "engine_id": engine_id,
                "expires_at": now + QUALITY_REPORT_CACHE_TTL_SECONDS,
                "value": report,
            }
        )
    return report


def clear_quality_report_cache() -> None:
    _quality_report_cache.update({"engine_id": None, "expires_at": 0.0, "value": None})


def build_quality_issue_workbook(report: dict[str, object]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "数据质量问题"
    sheet.append(["检查项", "记录ID", "店铺站点", "MSKU", "Listing", "负责人", "产品名称"])

    for issue in report.get("issues", []):
        label = issue.get("label")
        for row in issue.get("rows", []):
            sheet.append(
                [
                    label,
                    row.get("id"),
                    row.get("store_site"),
                    row.get("msku"),
                    row.get("listing"),
                    row.get("owner"),
                    row.get("product_name"),
                ]
            )

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _get_relation_issues(conn, store_site: str | None = None) -> list[dict[str, object]]:
    issues = []
    has_listing_owner_table = _listing_owner_table_available(conn)
    if has_listing_owner_table:
        issues.extend(_get_listing_owner_relation_issues(conn, store_site))
    else:
        issues.extend(_empty_listing_owner_relation_issues())

    if _store_site_table_available(conn):
        issues.extend(_get_store_site_relation_issues(conn, has_listing_owner_table, store_site))
    else:
        issues.extend(_empty_store_site_relation_issues())

    return issues


def _get_listing_owner_relation_issues(conn, store_site: str | None = None) -> list[dict[str, object]]:
    missing_where = """
        p.listing IS NOT NULL
        AND TRIM(p.listing) <> ''
        AND lo.id IS NULL
    """
    orphan_where = """
        p.id IS NULL
    """
    params = _store_site_params(store_site)
    product_store_site_filter = _store_site_filter("p", store_site)
    owner_store_site_filter = _store_site_filter("lo", store_site)
    missing_count = conn.execute(
        text(
            f"""
            SELECT COUNT(*)
            FROM amazon_product_info p
            LEFT JOIN amazon_listing_owner_config lo
              ON p.store_site = lo.store_site
             AND p.listing = lo.listing
            WHERE {missing_where}
            {product_store_site_filter}
            """
        ),
        params,
    ).scalar_one()
    missing_rows = [
        dict(row)
        for row in conn.execute(
            text(
                f"""
                SELECT p.id, p.store_site, p.msku, p.listing, p.product_name
                FROM amazon_product_info p
                LEFT JOIN amazon_listing_owner_config lo
                  ON p.store_site = lo.store_site
                 AND p.listing = lo.listing
                WHERE {missing_where}
                {product_store_site_filter}
                ORDER BY p.updated_at DESC, p.id DESC
                LIMIT 20
                """
            ),
            params,
        ).mappings()
    ]

    orphan_count = conn.execute(
        text(
            f"""
            SELECT COUNT(*)
            FROM amazon_listing_owner_config lo
            LEFT JOIN amazon_product_info p
              ON p.store_site = lo.store_site
             AND p.listing = lo.listing
            WHERE {orphan_where}
            {owner_store_site_filter}
            """
        ),
        params,
    ).scalar_one()
    orphan_rows = [
        dict(row)
        for row in conn.execute(
            text(
                f"""
                SELECT lo.id, lo.store_site, lo.listing, lo.owner
                FROM amazon_listing_owner_config lo
                LEFT JOIN amazon_product_info p
                  ON p.store_site = lo.store_site
                 AND p.listing = lo.listing
                WHERE {orphan_where}
                {owner_store_site_filter}
                ORDER BY lo.id DESC
                LIMIT 20
                """
            ),
            params,
        ).mappings()
    ]

    return [
        {
            "key": "missing_listing_owner_config",
            "label": "缺 Listing 负责人配置",
            "field": "listing",
            "count": missing_count,
            "rows": missing_rows,
        },
        {
            "key": "orphan_listing_owner_config",
            "label": "无产品使用的负责人配置",
            "field": "listing",
            "count": orphan_count,
            "rows": orphan_rows,
        },
    ]


def _get_store_site_relation_issues(
    conn,
    has_listing_owner_table: bool,
    store_site: str | None = None,
) -> list[dict[str, object]]:
    unknown_product_where = """
        p.store_site IS NOT NULL
        AND TRIM(p.store_site) <> ''
        AND ss.id IS NULL
    """
    unknown_owner_where = """
        lo.store_site IS NOT NULL
        AND TRIM(lo.store_site) <> ''
        AND ss.id IS NULL
    """
    params = _store_site_params(store_site)
    product_store_site_filter = _store_site_filter("p", store_site)
    owner_store_site_filter = _store_site_filter("lo", store_site)
    unknown_product_count = conn.execute(
        text(
            f"""
            SELECT COUNT(*)
            FROM amazon_product_info p
            LEFT JOIN amazon_store_site ss
              ON p.store_site = ss.store_site
            WHERE {unknown_product_where}
            {product_store_site_filter}
            """
        ),
        params,
    ).scalar_one()
    unknown_product_rows = [
        dict(row)
        for row in conn.execute(
            text(
                f"""
                SELECT p.id, p.store_site, p.msku, p.listing, p.product_name
                FROM amazon_product_info p
                LEFT JOIN amazon_store_site ss
                  ON p.store_site = ss.store_site
                WHERE {unknown_product_where}
                {product_store_site_filter}
                ORDER BY p.updated_at DESC, p.id DESC
                LIMIT 20
                """
            ),
            params,
        ).mappings()
    ]

    unknown_owner_count = 0
    unknown_owner_rows = []
    if has_listing_owner_table:
        unknown_owner_count = conn.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM amazon_listing_owner_config lo
                LEFT JOIN amazon_store_site ss
                  ON lo.store_site = ss.store_site
                WHERE {unknown_owner_where}
                {owner_store_site_filter}
                """
            ),
            params,
        ).scalar_one()
        unknown_owner_rows = [
            dict(row)
            for row in conn.execute(
                text(
                    f"""
                    SELECT lo.id, lo.store_site, lo.listing, lo.owner
                    FROM amazon_listing_owner_config lo
                    LEFT JOIN amazon_store_site ss
                      ON lo.store_site = ss.store_site
                    WHERE {unknown_owner_where}
                    {owner_store_site_filter}
                    ORDER BY lo.id DESC
                    LIMIT 20
                    """
                ),
                params,
            ).mappings()
        ]

    return [
        {
            "key": "unknown_product_store_site",
            "label": "产品引用未知店铺站点",
            "field": "store_site",
            "count": unknown_product_count,
            "rows": unknown_product_rows,
        },
        {
            "key": "unknown_listing_owner_store_site",
            "label": "负责人配置引用未知店铺站点",
            "field": "store_site",
            "count": unknown_owner_count,
            "rows": unknown_owner_rows,
        },
    ]


def _listing_owner_table_available(conn) -> bool:
    try:
        conn.execute(text("SELECT 1 FROM amazon_listing_owner_config LIMIT 1")).first()
        return True
    except SQLAlchemyError:
        return False


def _store_site_table_available(conn) -> bool:
    try:
        conn.execute(text("SELECT 1 FROM amazon_store_site LIMIT 1")).first()
        return True
    except SQLAlchemyError:
        return False


def _normalize_store_site(store_site: str | None) -> str | None:
    if store_site is None:
        return None
    store_site = store_site.strip()
    return store_site or None


def _store_site_params(store_site: str | None) -> dict[str, str]:
    return {"store_site": store_site} if store_site else {}


def _store_site_filter(alias: str, store_site: str | None) -> str:
    return f"AND {alias}.store_site = :store_site" if store_site else ""


def _empty_issues() -> list[dict[str, object]]:
    return _empty_field_issues() + _empty_relation_issues()


def _empty_field_issues() -> list[dict[str, object]]:
    return [
        {"key": key, "label": label, "field": field, "count": 0, "rows": []}
        for key, label, field in QUALITY_RULES
    ]


def _empty_relation_issues() -> list[dict[str, object]]:
    return _empty_listing_owner_relation_issues() + _empty_store_site_relation_issues()


def _empty_listing_owner_relation_issues() -> list[dict[str, object]]:
    return [
        {"key": key, "label": label, "field": "listing", "count": 0, "rows": []}
        for key, label in RELATION_RULES[:2]
    ]


def _empty_store_site_relation_issues() -> list[dict[str, object]]:
    return [
        {"key": key, "label": label, "field": "store_site", "count": 0, "rows": []}
        for key, label in RELATION_RULES[2:]
    ]


def _build_report(
    total: int,
    field_issues: list[dict[str, object]],
    relation_issues: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "total": total,
        "issues": field_issues + relation_issues,
        "field_issues": field_issues,
        "relation_issues": relation_issues,
    }
