import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.security import verify_password
from app.main import app


client = TestClient(app)


def create_operation_log_table(conn):
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


def test_admin_user_list_renders_rows_without_password_hash(monkeypatch):
    monkeypatch.setattr(
        "app.modules.admin_user.routes.list_admin_users",
        lambda: [
            {
                "id": 1,
                "username": "admin",
                "role": "admin",
                "is_active": 1,
                "created_at": "2026-06-01 10:00:00",
                "updated_at": "2026-06-01 10:30:00",
            },
            {
                "id": 2,
                "username": "viewer",
                "role": "viewer",
                "is_active": 0,
                "created_at": "2026-06-01 11:00:00",
                "updated_at": None,
            },
        ],
    )

    response = client.get("/admin-users")

    assert response.status_code == 200
    assert "admin" in response.text
    assert "viewer" in response.text
    assert "password_hash" not in response.text
    assert "/admin-users/1/edit" in response.text
    assert "/admin-users/1/reset-password" in response.text
    assert "启用" in response.text
    assert "停用" in response.text


def test_list_admin_users_returns_safe_fields(monkeypatch):
    from app.modules.admin_user import service

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO amazon_admin_user
                    (id, username, password_hash, role, is_active, created_at, updated_at)
                VALUES
                    (1, 'admin', 'secret-hash', 'admin', 1, '2026-06-01 10:00:00', NULL)
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    rows = service.list_admin_users()

    assert rows == [
        {
            "id": 1,
            "username": "admin",
            "role": "admin",
            "is_active": 1,
            "created_at": "2026-06-01 10:00:00",
            "updated_at": None,
        }
    ]


def test_admin_user_new_page_renders_create_form():
    response = client.get("/admin-users/new")

    assert response.status_code == 200
    assert "name=\"username\"" in response.text
    assert "name=\"password\"" in response.text
    assert "name=\"role\"" in response.text
    assert "name=\"is_active\"" in response.text


def test_admin_user_create_post_creates_user_and_redirects(monkeypatch):
    captured = {}

    def fake_create_admin_user(payload, changed_by="system"):
        captured["payload"] = payload
        captured["changed_by"] = changed_by
        return True

    monkeypatch.setattr("app.modules.admin_user.routes.create_admin_user", fake_create_admin_user)

    response = client.post(
        "/admin-users/new",
        data={
            "username": " new_user ",
            "password": "aa123123",
            "role": "viewer",
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin-users"
    assert captured["payload"] == {
        "username": "new_user",
        "password": "aa123123",
        "role": "viewer",
        "is_active": 1,
    }
    assert captured["changed_by"] == "test-admin"


def test_create_admin_user_hashes_password(monkeypatch):
    from app.modules.admin_user import service

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        create_operation_log_table(conn)

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert service.create_admin_user(
        {
            "username": "new_user",
            "password": "aa123123",
            "role": "viewer",
            "is_active": 1,
        }
    )

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username, password_hash, role, is_active FROM amazon_admin_user")
        ).mappings().one()

    assert row["username"] == "new_user"
    assert row["password_hash"] != "aa123123"
    assert verify_password("aa123123", row["password_hash"])
    assert row["role"] == "viewer"
    assert row["is_active"] == 1


def test_admin_user_edit_page_renders_role_and_status_only(monkeypatch):
    monkeypatch.setattr(
        "app.modules.admin_user.routes.get_admin_user",
        lambda user_id: {
            "id": user_id,
            "username": "viewer",
            "role": "viewer",
            "is_active": 1,
        },
    )

    response = client.get("/admin-users/2/edit")

    assert response.status_code == 200
    assert "viewer" in response.text
    assert "name=\"role\"" in response.text
    assert "name=\"is_active\"" in response.text
    assert "name=\"username\"" not in response.text
    assert "name=\"password\"" not in response.text


def test_admin_user_edit_post_updates_user_and_redirects(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.modules.admin_user.routes.get_admin_user",
        lambda user_id: {
            "id": user_id,
            "username": "viewer",
            "role": "viewer",
            "is_active": 1,
        },
    )

    def fake_update_admin_user(user_id, payload, changed_by="system"):
        captured["user_id"] = user_id
        captured["payload"] = payload
        captured["changed_by"] = changed_by
        return True

    monkeypatch.setattr("app.modules.admin_user.routes.update_admin_user", fake_update_admin_user)

    response = client.post(
        "/admin-users/2/edit",
        data={"username": "should_not_change", "role": "admin"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin-users"
    assert captured == {
        "user_id": 2,
        "payload": {"role": "admin", "is_active": 0},
        "changed_by": "test-admin",
    }


def test_update_admin_user_changes_role_and_status_only(monkeypatch):
    from app.modules.admin_user import service

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        create_operation_log_table(conn)
        conn.execute(
            text(
                """
                INSERT INTO amazon_admin_user
                    (id, username, password_hash, role, is_active, created_at, updated_at)
                VALUES
                    (2, 'viewer', 'secret-hash', 'viewer', 1, NULL, NULL)
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert service.update_admin_user(
        2,
        {
            "username": "should_not_change",
            "password": "plain-text",
            "role": "admin",
            "is_active": 0,
        },
    )

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username, password_hash, role, is_active FROM amazon_admin_user WHERE id = 2")
        ).mappings().one()

    assert row["username"] == "viewer"
    assert row["password_hash"] == "secret-hash"
    assert row["role"] == "admin"
    assert row["is_active"] == 0


def test_admin_user_reset_password_page_renders_password_only(monkeypatch):
    monkeypatch.setattr(
        "app.modules.admin_user.routes.get_admin_user",
        lambda user_id: {
            "id": user_id,
            "username": "viewer",
            "role": "viewer",
            "is_active": 1,
        },
    )

    response = client.get("/admin-users/2/reset-password")

    assert response.status_code == 200
    assert "viewer" in response.text
    assert "name=\"password\"" in response.text
    assert "name=\"username\"" not in response.text
    assert "name=\"role\"" not in response.text
    assert "name=\"is_active\"" not in response.text


def test_admin_user_reset_password_post_updates_password_and_redirects(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.modules.admin_user.routes.get_admin_user",
        lambda user_id: {
            "id": user_id,
            "username": "viewer",
            "role": "viewer",
            "is_active": 1,
        },
    )

    def fake_reset_admin_user_password(user_id, password, changed_by="system"):
        captured["user_id"] = user_id
        captured["password"] = password
        captured["changed_by"] = changed_by
        return True

    monkeypatch.setattr(
        "app.modules.admin_user.routes.reset_admin_user_password",
        fake_reset_admin_user_password,
    )

    response = client.post(
        "/admin-users/2/reset-password",
        data={"username": "should_not_change", "password": "new-pass"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin-users"
    assert captured == {"user_id": 2, "password": "new-pass", "changed_by": "test-admin"}


def test_reset_admin_user_password_updates_hash_only(monkeypatch):
    from app.modules.admin_user import service

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        create_operation_log_table(conn)
        conn.execute(
            text(
                """
                INSERT INTO amazon_admin_user
                    (id, username, password_hash, role, is_active, created_at, updated_at)
                VALUES
                    (2, 'viewer', 'old-hash', 'viewer', 1, NULL, NULL)
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert service.reset_admin_user_password(2, "new-pass")

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username, password_hash, role, is_active FROM amazon_admin_user WHERE id = 2")
        ).mappings().one()

    assert row["username"] == "viewer"
    assert row["password_hash"] != "new-pass"
    assert row["password_hash"] != "old-hash"
    assert verify_password("new-pass", row["password_hash"])
    assert row["role"] == "viewer"
    assert row["is_active"] == 1


def test_create_admin_user_writes_operation_log_without_password(monkeypatch):
    from app.modules.admin_user import service

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        create_operation_log_table(conn)

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert service.create_admin_user(
        {
            "username": "new_user",
            "password": "aa123123",
            "role": "viewer",
            "is_active": 1,
        },
        changed_by="admin",
    )

    with engine.connect() as conn:
        log = conn.execute(text("SELECT * FROM amazon_operation_log")).mappings().one()

    change_data = json.loads(log["change_data"])
    assert log["table_name"] == "amazon_admin_user"
    assert log["record_id"] == 1
    assert log["operation_type"] == "INSERT"
    assert log["changed_by"] == "admin"
    assert change_data == {
        "username": {"old": None, "new": "new_user"},
        "role": {"old": None, "new": "viewer"},
        "is_active": {"old": None, "new": 1},
    }
    assert "password" not in log["change_data"]
    assert "password_hash" not in log["change_data"]
    assert "aa123123" not in log["change_data"]


def test_update_admin_user_writes_change_log(monkeypatch):
    from app.modules.admin_user import service

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        create_operation_log_table(conn)
        conn.execute(
            text(
                """
                INSERT INTO amazon_admin_user
                    (id, username, password_hash, role, is_active, created_at, updated_at)
                VALUES
                    (2, 'viewer', 'secret-hash', 'viewer', 1, NULL, NULL)
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert service.update_admin_user(
        2,
        {"role": "admin", "is_active": 0},
        changed_by="admin",
    )

    with engine.connect() as conn:
        log = conn.execute(text("SELECT * FROM amazon_operation_log")).mappings().one()

    assert log["table_name"] == "amazon_admin_user"
    assert log["record_id"] == 2
    assert log["operation_type"] == "UPDATE"
    assert log["changed_by"] == "admin"
    assert json.loads(log["change_data"]) == {
        "role": {"old": "viewer", "new": "admin"},
        "is_active": {"old": 1, "new": 0},
    }


def test_update_admin_user_does_not_log_when_unchanged(monkeypatch):
    from app.modules.admin_user import service

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        create_operation_log_table(conn)
        conn.execute(
            text(
                """
                INSERT INTO amazon_admin_user
                    (id, username, password_hash, role, is_active, created_at, updated_at)
                VALUES
                    (2, 'viewer', 'secret-hash', 'viewer', 1, NULL, NULL)
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert service.update_admin_user(2, {"role": "viewer", "is_active": 1}, changed_by="admin")

    with engine.connect() as conn:
        log_count = conn.execute(text("SELECT COUNT(*) FROM amazon_operation_log")).scalar_one()

    assert log_count == 0


def test_reset_admin_user_password_writes_safe_operation_log(monkeypatch):
    from app.modules.admin_user import service

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE amazon_admin_user (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        create_operation_log_table(conn)
        conn.execute(
            text(
                """
                INSERT INTO amazon_admin_user
                    (id, username, password_hash, role, is_active, created_at, updated_at)
                VALUES
                    (2, 'viewer', 'old-hash', 'viewer', 1, NULL, NULL)
                """
            )
        )

    monkeypatch.setattr(service, "get_engine", lambda: engine)

    assert service.reset_admin_user_password(2, "new-pass", changed_by="admin")

    with engine.connect() as conn:
        log = conn.execute(text("SELECT * FROM amazon_operation_log")).mappings().one()

    assert log["table_name"] == "amazon_admin_user"
    assert log["record_id"] == 2
    assert log["operation_type"] == "RESET_PASSWORD"
    assert log["changed_by"] == "admin"
    assert json.loads(log["change_data"]) == {
        "password": {"old": None, "new": "RESET"}
    }
    assert "new-pass" not in log["change_data"]
    assert "old-hash" not in log["change_data"]
    assert "password_hash" not in log["change_data"]
