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
)


def get_product_quality_report() -> dict[str, object]:
    engine = get_engine()
    if engine is None:
        return {"total": 0, "issues": _empty_issues()}
    now = monotonic()
    engine_id = id(engine)
    if (
        _quality_report_cache["engine_id"] == engine_id
        and _quality_report_cache["value"] is not None
        and now < _quality_report_cache["expires_at"]
    ):
        return _quality_report_cache["value"]

    total_sql = text("SELECT COUNT(*) FROM amazon_product_info")

    with engine.connect() as conn:
        total = conn.execute(total_sql).scalar_one()
        issues = []
        for key, label, field in QUALITY_RULES:
            where_sql = f"{field} IS NULL OR TRIM({field}) = ''"
            count = conn.execute(
                text(f"SELECT COUNT(*) FROM amazon_product_info WHERE {where_sql}")
            ).scalar_one()
            rows = [
                dict(row)
                for row in conn.execute(
                    text(
                        f"""
                        SELECT id, store_site, msku, product_name
                        FROM amazon_product_info
                        WHERE {where_sql}
                        ORDER BY updated_at DESC, id DESC
                        LIMIT 20
                        """
                    )
                ).mappings()
            ]
            issues.append(
                {
                    "key": key,
                    "label": label,
                    "field": field,
                    "count": count,
                    "rows": rows,
                }
            )
        issues.extend(_get_relation_issues(conn))

    report = {"total": total, "issues": issues}
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


def _get_relation_issues(conn) -> list[dict[str, object]]:
    if not _listing_owner_table_available(conn):
        return _empty_relation_issues()

    missing_where = """
        p.listing IS NOT NULL
        AND TRIM(p.listing) <> ''
        AND lo.id IS NULL
    """
    orphan_where = """
        p.id IS NULL
    """
    missing_count = conn.execute(
        text(
            f"""
            SELECT COUNT(*)
            FROM amazon_product_info p
            LEFT JOIN amazon_listing_owner_config lo
              ON p.store_site = lo.store_site
             AND p.listing = lo.listing
            WHERE {missing_where}
            """
        )
    ).scalar_one()
    missing_rows = [
        dict(row)
        for row in conn.execute(
            text(
                f"""
                SELECT p.id, p.store_site, p.msku, p.product_name
                FROM amazon_product_info p
                LEFT JOIN amazon_listing_owner_config lo
                  ON p.store_site = lo.store_site
                 AND p.listing = lo.listing
                WHERE {missing_where}
                ORDER BY p.updated_at DESC, p.id DESC
                LIMIT 20
                """
            )
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
            """
        )
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
                ORDER BY lo.id DESC
                LIMIT 20
                """
            )
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


def _listing_owner_table_available(conn) -> bool:
    try:
        conn.execute(text("SELECT 1 FROM amazon_listing_owner_config LIMIT 1")).first()
        return True
    except SQLAlchemyError:
        return False


def _empty_issues() -> list[dict[str, object]]:
    return [
        {"key": key, "label": label, "field": field, "count": 0, "rows": []}
        for key, label, field in QUALITY_RULES
    ] + _empty_relation_issues()


def _empty_relation_issues() -> list[dict[str, object]]:
    return [
        {"key": key, "label": label, "field": "listing", "count": 0, "rows": []}
        for key, label in RELATION_RULES
    ]
