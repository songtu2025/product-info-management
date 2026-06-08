from pathlib import Path


def test_main_schema_includes_user_preference_table():
    schema_sql = Path("sql/建表语句.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE amazon_user_preference" in schema_sql
    assert "PRIMARY KEY (username, preference_key)" in schema_sql
