from sqlalchemy import text

from app.core.db import get_engine


QUALITY_RULES = (
    ("missing_asin", "缺 ASIN", "asin"),
    ("missing_listing", "缺 Listing", "listing"),
    ("missing_brand", "缺品牌", "brand"),
    ("missing_sales_status", "缺销售状态", "sales_status"),
    ("missing_product_name", "缺产品名称", "product_name"),
)


def get_product_quality_report() -> dict[str, object]:
    engine = get_engine()
    if engine is None:
        return {"total": 0, "issues": _empty_issues()}

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

    return {"total": total, "issues": issues}


def _empty_issues() -> list[dict[str, object]]:
    return [
        {"key": key, "label": label, "field": field, "count": 0, "rows": []}
        for key, label, field in QUALITY_RULES
    ]
