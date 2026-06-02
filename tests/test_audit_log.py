import json

from sqlalchemy import create_engine, text

from app.modules.product_info import service
from app.modules.product_info.service import create_product, update_product
from app.shared.audit import build_change_set


def test_build_change_set_keeps_only_changed_values():
    changes = build_change_set(
        {"product_name": "Old", "brand": "BrandA", "label_name": None},
        {"product_name": "New", "brand": "BrandA", "label_name": "标签"},
    )

    assert changes == {
        "product_name": {"old": "Old", "new": "New"},
        "label_name": {"old": None, "new": "标签"},
    }


def test_update_product_writes_operation_log(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY,
                    product_name TEXT,
                    brand TEXT,
                    sales_status TEXT,
                    storage_type TEXT,
                    category_level_1 TEXT,
                    category_a TEXT,
                    category_b TEXT,
                    label_name TEXT,
                    msku_shipping_remark TEXT,
                    transfer_remark TEXT,
                    msku_lock_status TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE amazon_operation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    operation_type TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    change_data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_product_info (
                    id, product_name, brand, sales_status, storage_type,
                    category_level_1, category_a, category_b, label_name,
                    msku_shipping_remark, transfer_remark, msku_lock_status
                )
                VALUES (
                    1, 'Old Product', 'BrandA', '在售', 'FBA',
                    '服饰', '眼镜', '太阳镜', NULL,
                    NULL, NULL, '否'
                )
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert update_product(1, {"product_name": "New Product", "brand": "BrandA"})

    with engine.connect() as conn:
        product_name = conn.execute(
            text("SELECT product_name FROM amazon_product_info WHERE id = 1")
        ).scalar_one()
        log = conn.execute(text("SELECT * FROM amazon_operation_log")).mappings().one()

    assert product_name == "New Product"
    assert log["table_name"] == "amazon_product_info"
    assert log["record_id"] == 1
    assert log["operation_type"] == "UPDATE"
    assert log["changed_by"] == "system"
    assert json.loads(log["change_data"]) == {
        "product_name": {"old": "Old Product", "new": "New Product"}
    }


def test_create_product_inserts_row_and_writes_operation_log(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_product_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT,
                    msku TEXT NOT NULL,
                    store_site TEXT NOT NULL,
                    parent_asin TEXT,
                    product_name TEXT,
                    sku TEXT,
                    brand TEXT,
                    fnsku TEXT,
                    sales_status TEXT,
                    storage_type TEXT,
                    category_level_1 TEXT,
                    category_a TEXT,
                    category_b TEXT,
                    listing TEXT,
                    label_name TEXT,
                    msku_shipping_remark TEXT,
                    transfer_remark TEXT,
                    msku_lock_status TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE amazon_operation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    operation_type TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    change_data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    product_id = create_product(
        {
            "store_site": "SAYOLA:US",
            "msku": "MSKU-NEW",
            "asin": "B012345678",
            "product_name": "New Product",
            "brand": None,
        },
        changed_by="admin",
    )

    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM amazon_product_info")).mappings().one()
        log = conn.execute(text("SELECT * FROM amazon_operation_log")).mappings().one()

    assert product_id == 1
    assert row["store_site"] == "SAYOLA:US"
    assert row["msku"] == "MSKU-NEW"
    assert row["product_name"] == "New Product"
    assert log["table_name"] == "amazon_product_info"
    assert log["record_id"] == 1
    assert log["operation_type"] == "INSERT"
    assert log["changed_by"] == "admin"
    assert json.loads(log["change_data"]) == {
        "store_site": {"old": None, "new": "SAYOLA:US"},
        "msku": {"old": None, "new": "MSKU-NEW"},
        "asin": {"old": None, "new": "B012345678"},
        "product_name": {"old": None, "new": "New Product"},
    }
