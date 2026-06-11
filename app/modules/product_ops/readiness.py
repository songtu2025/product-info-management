def build_purchase_readiness(
    overview: dict[str, object],
    allocation_rows: list[dict[str, object]] | None = None,
    forecast_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    missing_reasons = _missing_reasons(overview)
    if missing_reasons:
        return {
            "status": "blocked",
            "label": "需补数据",
            "message": "采购判断前需要先补齐基础经营数据",
            "reasons": missing_reasons,
        }

    review_reasons = _review_reasons(overview, allocation_rows, forecast_rows)
    if review_reasons:
        return {
            "status": "review",
            "label": "需人工确认",
            "message": "存在异常数据，需确认后再进入采购判断",
            "reasons": review_reasons,
        }

    return {
        "status": "ready",
        "label": "可进入采购判断",
        "message": "基础经营数据已满足采购判断前置条件",
        "reasons": [],
    }


def flatten_purchase_readiness(row: dict[str, object], readiness: dict[str, object]) -> None:
    reasons = readiness.get("reasons") or []
    row["purchase_readiness"] = readiness
    row["purchase_readiness_status"] = readiness.get("status")
    row["purchase_readiness_label"] = readiness.get("label")
    row["purchase_readiness_reasons"] = "、".join(str(reason) for reason in reasons)


def _missing_reasons(overview: dict[str, object]) -> list[str]:
    reasons = []
    if not _has_owner_config(overview):
        reasons.append("缺负责人配置")
    if _number(overview.get("product_msku_count")) <= 0:
        reasons.append("缺产品信息")
    if _number(overview.get("allocation_msku_count")) <= 0:
        reasons.append("缺销占比")
    if _number(overview.get("forecast_month_count")) <= 0:
        reasons.append("缺销售预估")
    return reasons


def _review_reasons(
    overview: dict[str, object],
    allocation_rows: list[dict[str, object]] | None,
    forecast_rows: list[dict[str, object]] | None,
) -> list[str]:
    reasons = []
    if _zero_allocation_count(overview, allocation_rows) > 0:
        reasons.append("销占比为0")
    if _zero_forecast_count(overview, forecast_rows) > 0:
        reasons.append("销售预估为0")
    return reasons


def _has_owner_config(overview: dict[str, object]) -> bool:
    return bool(
        overview.get("owner_config_id")
        or overview.get("owner")
        or overview.get("listing_status")
        or overview.get("listing_maintainer")
    )


def _zero_allocation_count(
    overview: dict[str, object],
    allocation_rows: list[dict[str, object]] | None,
) -> int:
    if allocation_rows is not None:
        return sum(
            1
            for row in allocation_rows
            if _is_zero_ratio(row.get("style_sales_ratio")) or _is_zero_ratio(row.get("sku_sales_ratio"))
        )
    return int(_number(overview.get("zero_allocation_ratio_count")))


def _zero_forecast_count(
    overview: dict[str, object],
    forecast_rows: list[dict[str, object]] | None,
) -> int:
    if forecast_rows is not None:
        return sum(1 for row in forecast_rows if _is_zero_forecast_units(row.get("forecast_units")))
    return int(_number(overview.get("zero_forecast_units_count")))


def _is_zero_ratio(value: object) -> bool:
    if value is None:
        return True
    try:
        return float(value) == 0
    except (TypeError, ValueError):
        return False


def _is_zero_forecast_units(value: object) -> bool:
    if value is None:
        return True
    try:
        return float(value) <= 0
    except (TypeError, ValueError):
        return False


def _number(value: object) -> float:
    if value is None:
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0
