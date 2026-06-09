from app.modules.data_quality.service import get_product_quality_summary
from app.modules.product_info.service import ProductFilters, get_filter_options, list_products
from app.shared.user_preference import get_user_preferences


PRODUCT_INFO_PREFERENCE_KEYS = (
    "product_info.export.fields",
    "product_info.list.columns",
    "product_info.filter.views",
)


def warm_product_info_caches(usernames: tuple[str, ...] = ("admin", "test-admin")) -> None:
    list_products(ProductFilters())
    get_filter_options()
    get_product_quality_summary()
    for username in usernames:
        get_user_preferences(username, PRODUCT_INFO_PREFERENCE_KEYS)
