import sqlite3
from pathlib import Path

import pytest

from course2career.auth_service import (
    AdminBootstrapError,
    AuthService,
    InvalidCredentialsError,
    RegistrationError,
)
from course2career.permissions import Plan, Role
from course2career.user_repository import SQLiteUserRepository


@pytest.fixture
def repository(tmp_path: Path) -> SQLiteUserRepository:
    return SQLiteUserRepository(tmp_path / "test.db")


def test_register_creates_normal_user_and_hashes_password(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)

    principal = service.register("student_01", "strong-pass-123")

    assert principal.role == Role.USER
    assert principal.plan == Plan.FREE
    assert principal.user_id
    with sqlite3.connect(repository.database_path) as connection:
        stored_hash = connection.execute(
            "SELECT password_hash FROM users WHERE id = ?", (principal.user_id,)
        ).fetchone()[0]
    assert stored_hash != "strong-pass-123"
    assert "strong-pass-123" not in stored_hash


def test_authenticate_accepts_correct_password_and_rejects_wrong_one(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    registered = service.register("student_01", "strong-pass-123")

    authenticated = service.authenticate("STUDENT_01", "strong-pass-123")

    assert authenticated == registered
    with pytest.raises(InvalidCredentialsError, match="用户名或密码错误"):
        service.authenticate("student_01", "wrong-password")


def test_register_rejects_duplicate_username_and_weak_password(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    service.register("student_01", "strong-pass-123")

    with pytest.raises(RegistrationError, match="已存在"):
        service.register("STUDENT_01", "another-pass-123")
    with pytest.raises(RegistrationError, match="至少需要 8"):
        service.register("student_02", "short")


def test_bootstrap_admin_creates_admin_without_storing_plaintext_password(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)

    principal = service.ensure_bootstrap_admin(
        "course2career_admin", "unique-admin-pass-123"
    )

    assert principal.role == Role.ADMIN
    assert principal.plan == Plan.ADMIN
    assert (
        service.authenticate("course2career_admin", "unique-admin-pass-123")
        == principal
    )
    with sqlite3.connect(repository.database_path) as connection:
        stored_hash = connection.execute(
            "SELECT password_hash FROM users WHERE id = ?", (principal.user_id,)
        ).fetchone()[0]
    assert stored_hash != "unique-admin-pass-123"
    assert "unique-admin-pass-123" not in stored_hash


def test_bootstrap_admin_is_idempotent_and_does_not_reset_password(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    first = service.ensure_bootstrap_admin(
        "course2career_admin", "unique-admin-pass-123"
    )

    second = service.ensure_bootstrap_admin(
        "course2career_admin", "different-admin-pass-456"
    )

    assert second == first
    assert service.authenticate("course2career_admin", "unique-admin-pass-123") == first
    with pytest.raises(InvalidCredentialsError):
        service.authenticate("course2career_admin", "different-admin-pass-456")


def test_bootstrap_admin_refuses_to_promote_an_existing_normal_user(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    service.register("course2career_admin", "normal-user-pass-123")

    with pytest.raises(AdminBootstrapError, match="已被普通账户占用"):
        service.ensure_bootstrap_admin("course2career_admin", "unique-admin-pass-123")
