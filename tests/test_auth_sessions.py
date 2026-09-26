"""Durable, revocable opaque login sessions on both database backends."""

import hashlib
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import pytest

from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.database_migrations import schema_version
from course2career.permissions import Plan, Role
from course2career.postgres_repository import PostgresProductRepository
from course2career.product_repository import SQLiteProductRepository


def test_sqlite_session_is_hashed_restorable_and_revocable(tmp_path, caplog):
    repo = SQLiteProductRepository(tmp_path / "sessions.db")
    auth = AuthService(repo)
    principal = auth.register("alice", "synthetic-password-123")
    now = datetime.now(UTC)
    token = auth.create_session(principal, now=now)
    second_token = auth.create_session(principal, now=now)

    assert len(token) == 43
    assert second_token != token
    assert auth.restore_session(token, now=now + timedelta(days=1)) == principal
    assert auth.restore_session("A" * 43) is None
    assert auth.restore_session(token, now=now + timedelta(days=8)) is None
    with sqlite3.connect(repo.database_path) as connection:
        stored = connection.execute(
            "SELECT token_hash, expires_time FROM auth_sessions WHERE token_hash = ?",
            (hashlib.sha256(token.encode("ascii")).hexdigest(),),
        ).fetchone()
        assert stored[0] == hashlib.sha256(token.encode("ascii")).hexdigest()
        assert token not in "".join(connection.iterdump())
        assert datetime.fromisoformat(stored[1]) == now + timedelta(days=7)
    assert token not in caplog.text
    auth.revoke_session(token)
    assert auth.restore_session(token) is None


def test_session_user_isolation_status_rotation_and_live_role(tmp_path):
    repo = SQLiteProductRepository(tmp_path / "isolation.db")
    auth = AuthService(repo)
    alice = auth.register("alice", "synthetic-password-123")
    bob = auth.register("bob", "synthetic-password-456")
    alice_token = auth.create_session(alice)
    bob_token = auth.create_session(bob)
    assert auth.restore_session(alice_token).user_id == alice.user_id
    assert auth.restore_session(bob_token).user_id == bob.user_id

    # The cookie carries no role or plan: those fields come from the users table.
    with repo._connect() as connection:
        connection.execute(
            "UPDATE users SET role = 'admin', plan = 'admin' WHERE id = ?",
            (alice.user_id,),
        )
    restored = auth.restore_session(alice_token)
    assert restored.role == Role.ADMIN
    assert restored.plan == Plan.ADMIN
    assert auth.restore_session(bob_token).role == Role.USER

    with repo._connect() as connection:
        connection.execute(
            "UPDATE users SET status = 'disabled' WHERE id = ?", (alice.user_id,)
        )
    assert auth.restore_session(alice_token) is None
    with repo._connect() as connection:
        connection.execute(
            "UPDATE users SET status = 'active' WHERE id = ?", (alice.user_id,)
        )
    repo.update_password_hash(alice.user_id, "synthetic-new-hash")
    assert auth.restore_session(alice_token) is None
    assert auth.restore_session(bob_token).user_id == bob.user_id
    with repo._connect() as connection:
        connection.execute("DELETE FROM users WHERE id = ?", (bob.user_id,))
    assert auth.restore_session(bob_token) is None


def test_developer_mode_is_restored_from_database(tmp_path):
    repo = SQLiteProductRepository(tmp_path / "developer.db")
    auth = AuthService(repo)
    user = auth.register("developer", "synthetic-password-123")
    BYOKModeService(repo).set_enabled(user, True)
    self_service_token = auth.create_session(user)
    assert auth.restore_session(self_service_token).byok_enabled
    repo.update_membership(user.user_id, Role.DEVELOPER, Plan.DEVELOPER)
    assert auth.restore_session(self_service_token) is None
    current = auth.authenticate("developer", "synthetic-password-123")
    token = auth.create_session(current)
    restored = auth.restore_session(token)
    assert restored.role == Role.DEVELOPER
    assert restored.plan == Plan.DEVELOPER
    assert restored.byok_enabled


def test_sqlite_v2_upgrade_is_additive(tmp_path):
    path = tmp_path / "existing.db"
    repo = SQLiteProductRepository(path)
    user = AuthService(repo).register("existing", "synthetic-password-123")
    with repo._connect() as connection:
        connection.execute("DROP TABLE auth_sessions")
        connection.execute("DELETE FROM schema_migrations WHERE version = 3")
    upgraded = SQLiteProductRepository(path)
    assert schema_version(upgraded.backend) == 3
    assert upgraded.find_by_id(user.user_id) is not None
    assert AuthService(upgraded).restore_session("A" * 43) is None


@pytest.mark.postgres
def test_postgres_session_round_trip_and_v2_upgrade():
    url = os.getenv("C08_TEST_DATABASE_URL")
    if not url or urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("仅在 CI 本机合成 PostgreSQL 测试库执行")
    repo = PostgresProductRepository(url, allow_insecure_local_test=True)
    auth = AuthService(repo)
    user = auth.register("session_test_user", "synthetic-password-123")
    token = auth.create_session(user)
    try:
        assert auth.restore_session(token) == user
        with repo._connect() as connection:
            row = connection.execute(
                "SELECT token_hash FROM auth_sessions WHERE user_id = ?",
                (user.user_id,),
            ).fetchone()
            assert row["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
        auth.revoke_session(token)
        assert auth.restore_session(token) is None
    finally:
        with repo._connect() as connection:
            connection.execute("DELETE FROM users WHERE id = ?", (user.user_id,))
    with repo._connect() as connection:
        connection.execute("DROP TABLE auth_sessions")
        connection.execute("DELETE FROM schema_migrations WHERE version = 3")
    upgraded = PostgresProductRepository(url, allow_insecure_local_test=True)
    assert schema_version(upgraded.backend) == 3
    assert upgraded.count_users() >= 0
