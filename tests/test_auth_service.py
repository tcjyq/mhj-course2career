import sqlite3
from pathlib import Path

import pytest

from course2career.auth_service import (
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
