from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import get_engine
from app.core.security import hash_password
from app.shared.audit import build_change_set, record_operation_log


VALID_ROLES = {"admin", "viewer"}


def list_admin_users() -> list[dict[str, object]]:
    engine = get_engine()
    if engine is None:
        return []

    sql = text(
        """
        SELECT id, username, role, is_active, created_at, updated_at
        FROM amazon_admin_user
        ORDER BY id DESC
        LIMIT 200
        """
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(sql).mappings()]


def get_admin_user(user_id: int) -> dict[str, object] | None:
    engine = get_engine()
    if engine is None:
        return None

    sql = text(
        """
        SELECT id, username, role, is_active, created_at, updated_at
        FROM amazon_admin_user
        WHERE id = :user_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"user_id": user_id}).mappings().first()
    return dict(row) if row else None


def create_admin_user(payload: dict[str, object], changed_by: str = "system") -> bool:
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    role = str(payload.get("role") or "").strip()
    is_active = 1 if payload.get("is_active") else 0
    if not username or not password or role not in VALID_ROLES:
        return False

    engine = get_engine()
    if engine is None:
        return False

    sql = text(
        """
        INSERT INTO amazon_admin_user (
            username,
            password_hash,
            role,
            is_active
        )
        VALUES (
            :username,
            :password_hash,
            :role,
            :is_active
        )
        """
    )
    try:
        with engine.begin() as conn:
            result = conn.execute(
                sql,
                {
                    "username": username,
                    "password_hash": hash_password(password),
                    "role": role,
                    "is_active": is_active,
                },
            )
            record_operation_log(
                conn,
                table_name="amazon_admin_user",
                record_id=result.lastrowid,
                operation_type="INSERT",
                changed_by=changed_by,
                change_data={
                    "username": {"old": None, "new": username},
                    "role": {"old": None, "new": role},
                    "is_active": {"old": None, "new": is_active},
                },
            )
    except IntegrityError:
        return False
    return True


def update_admin_user(
    user_id: int,
    payload: dict[str, object],
    changed_by: str = "system",
) -> bool:
    role = str(payload.get("role") or "").strip()
    is_active = 1 if payload.get("is_active") else 0
    if role not in VALID_ROLES:
        return False

    engine = get_engine()
    if engine is None:
        return False

    select_sql = text(
        """
        SELECT role, is_active
        FROM amazon_admin_user
        WHERE id = :user_id
        """
    )
    update_sql = text(
        """
        UPDATE amazon_admin_user
        SET role = :role,
            is_active = :is_active
        WHERE id = :user_id
        """
    )
    with engine.begin() as conn:
        before = conn.execute(select_sql, {"user_id": user_id}).mappings().first()
        if before is None:
            return False

        after = {"role": role, "is_active": is_active}
        changes = build_change_set(dict(before), after)
        if not changes:
            return True

        result = conn.execute(
            update_sql,
            {
                "user_id": user_id,
                "role": role,
                "is_active": is_active,
            },
        )
        if result.rowcount > 0:
            record_operation_log(
                conn,
                table_name="amazon_admin_user",
                record_id=user_id,
                operation_type="UPDATE",
                changed_by=changed_by,
                change_data=changes,
            )
    return result.rowcount > 0


def reset_admin_user_password(
    user_id: int,
    password: str,
    changed_by: str = "system",
) -> bool:
    password = password.strip()
    if not password:
        return False

    engine = get_engine()
    if engine is None:
        return False

    sql = text(
        """
        UPDATE amazon_admin_user
        SET password_hash = :password_hash
        WHERE id = :user_id
        """
    )
    with engine.begin() as conn:
        result = conn.execute(
            sql,
            {
                "user_id": user_id,
                "password_hash": hash_password(password),
            },
        )
        if result.rowcount > 0:
            record_operation_log(
                conn,
                table_name="amazon_admin_user",
                record_id=user_id,
                operation_type="RESET_PASSWORD",
                changed_by=changed_by,
                change_data={"password": {"old": None, "new": "RESET"}},
            )
    return result.rowcount > 0
