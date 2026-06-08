import hashlib
import hmac
import os
from dataclasses import dataclass

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.core.db import get_engine
from app.shared.audit import record_operation_log


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: str


PUBLIC_PATHS = ("/login", "/health", "/static")


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_text),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def authenticate_user(username: str, password: str) -> AuthUser | None:
    engine = get_engine()
    if engine is None:
        return None

    query = text(
        """
        SELECT username, password_hash, role
        FROM amazon_admin_user
        WHERE username = :username AND is_active = 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query, {"username": username}).mappings().first()

    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return AuthUser(username=row["username"], role=row["role"])


def change_user_password(username: str, current_password: str, new_password: str) -> bool:
    if not username or not current_password or not new_password:
        return False

    engine = get_engine()
    if engine is None:
        return False

    select_sql = text(
        """
        SELECT id, password_hash
        FROM amazon_admin_user
        WHERE username = :username AND is_active = 1
        """
    )
    update_sql = text(
        """
        UPDATE amazon_admin_user
        SET password_hash = :password_hash
        WHERE id = :user_id
        """
    )
    with engine.begin() as conn:
        row = conn.execute(select_sql, {"username": username}).mappings().first()
        if row is None or not verify_password(current_password, row["password_hash"]):
            return False

        result = conn.execute(
            update_sql,
            {
                "user_id": row["id"],
                "password_hash": hash_password(new_password),
            },
        )
        if result.rowcount > 0:
            record_operation_log(
                conn,
                table_name="amazon_admin_user",
                record_id=row["id"],
                operation_type="CHANGE_PASSWORD",
                changed_by=username,
                change_data={"password": {"old": None, "new": "CHANGED"}},
            )
    return result.rowcount > 0


def current_user(request: Request) -> AuthUser | None:
    data = request.session.get("user")
    if not data:
        return None
    return AuthUser(username=data["username"], role=data["role"])


def require_admin(request: Request) -> AuthUser:
    if getattr(request.app.state, "disable_auth", False):
        return AuthUser(username="test-admin", role="admin")

    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


async def auth_middleware(request: Request, call_next):
    if getattr(request.app.state, "disable_auth", False):
        return await call_next(request)

    path = request.url.path
    if path.startswith(PUBLIC_PATHS) or path == "/favicon.ico":
        return await call_next(request)

    if current_user(request) is None:
        return RedirectResponse(f"/login?next={path}", status_code=303)

    return await call_next(request)
