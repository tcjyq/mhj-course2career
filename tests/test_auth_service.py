import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from course2career.auth_service import (
    AdminBootstrapError,
    AuthService,
    InvalidCredentialsError,
    InvalidSessionError,
    RegistrationError,
    TooManyLoginAttemptsError,
)
from course2career.password_security import hash_password
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


def test_bootstrap_admin_is_idempotent_when_password_is_unchanged(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    first = service.ensure_bootstrap_admin(
        "course2career_admin", "unique-admin-pass-123"
    )

    second = service.ensure_bootstrap_admin(
        "course2career_admin", "unique-admin-pass-123"
    )

    assert second == first
    assert service.authenticate("course2career_admin", "unique-admin-pass-123") == first


def test_bootstrap_admin_rotates_changed_password_and_invalidates_old_session(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    old_principal = service.ensure_bootstrap_admin(
        "course2career_admin", "unique-admin-pass-123"
    )

    rotated_principal = service.ensure_bootstrap_admin(
        "course2career_admin", "rotated-admin-pass-456"
    )

    assert rotated_principal.user_id == old_principal.user_id
    assert rotated_principal.session_version == old_principal.session_version + 1
    with pytest.raises(InvalidCredentialsError):
        service.authenticate("course2career_admin", "unique-admin-pass-123")
    assert (
        service.authenticate("course2career_admin", "rotated-admin-pass-456")
        == rotated_principal
    )
    with pytest.raises(InvalidSessionError):
        service.refresh_principal(old_principal)
    assert service.refresh_principal(rotated_principal) == rotated_principal


def test_authenticate_rate_limits_repeated_failures_per_browser_session(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    service.register("student_01", "strong-pass-123")
    start = datetime(2026, 7, 25, 12, tzinfo=UTC)

    for attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            service.authenticate(
                "student_01",
                "wrong-password",
                attempt_scope="browser-session",
                now=start + timedelta(seconds=attempt),
            )

    with pytest.raises(TooManyLoginAttemptsError, match="稍后再试"):
        service.authenticate(
            "student_01",
            "strong-pass-123",
            attempt_scope="browser-session",
            now=start + timedelta(minutes=1),
        )

    authenticated = service.authenticate(
        "student_01",
        "strong-pass-123",
        attempt_scope="browser-session",
        now=start + timedelta(minutes=16),
    )
    assert authenticated.username == "student_01"


def test_bootstrap_admin_does_not_create_second_admin_when_username_changes(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    first = service.ensure_bootstrap_admin(
        "course2career_admin", "unique-admin-pass-123"
    )

    result = service.ensure_bootstrap_admin("another_admin", "different-admin-pass-456")

    assert result == first
    with sqlite3.connect(repository.database_path) as connection:
        admin_count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]
    assert admin_count == 1


def test_bootstrap_admin_refuses_to_promote_an_existing_normal_user(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    service.register("course2career_admin", "normal-user-pass-123")

    with pytest.raises(AdminBootstrapError, match="已被普通账户占用"):
        service.ensure_bootstrap_admin("course2career_admin", "unique-admin-pass-123")


def test_bootstrap_admin_accepts_prehashed_password_and_authenticates(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)
    encoded_hash = hash_password("unique-admin-pass-123")

    principal = service.ensure_bootstrap_admin(
        "course2career_admin",
        password_hash=encoded_hash,
    )

    assert principal.role == Role.ADMIN
    assert principal.plan == Plan.ADMIN
    assert (
        service.authenticate("course2career_admin", "unique-admin-pass-123")
        == principal
    )
    with pytest.raises(InvalidCredentialsError, match="用户名或密码错误"):
        service.authenticate("course2career_admin", "wrong-admin-password")
    with sqlite3.connect(repository.database_path) as connection:
        stored_hash = connection.execute(
            "SELECT password_hash FROM users WHERE id = ?", (principal.user_id,)
        ).fetchone()[0]
    assert stored_hash == encoded_hash


def test_bootstrap_admin_supports_repository_from_rolling_deployment(
    repository: SQLiteUserRepository,
) -> None:
    @dataclass(frozen=True)
    class LegacyStoredUser:
        id: str
        username: str
        username_normalized: str
        password_hash: str
        role: Role
        plan: Plan
        created_time: str

    class LegacyRepository:
        def add(self, user) -> None:
            repository.add(user)

        def find_by_normalized_username(self, username):
            user = repository.find_by_normalized_username(username)
            if user is None:
                return None
            return LegacyStoredUser(
                id=user.id,
                username=user.username,
                username_normalized=user.username_normalized,
                password_hash=user.password_hash,
                role=user.role,
                plan=user.plan,
                created_time=user.created_time,
            )

        def find_by_id(self, user_id):
            user = repository.find_by_id(user_id)
            if user is None:
                return None
            return LegacyStoredUser(
                id=user.id,
                username=user.username,
                username_normalized=user.username_normalized,
                password_hash=user.password_hash,
                role=user.role,
                plan=user.plan,
                created_time=user.created_time,
            )

    service = AuthService(LegacyRepository())  # type: ignore[arg-type]

    principal = service.ensure_bootstrap_admin(
        "course2career_admin",
        "unique-admin-pass-123",
    )

    assert principal.role == Role.ADMIN
    assert (
        service.authenticate("course2career_admin", "unique-admin-pass-123")
        == principal
    )


def test_bootstrap_admin_rejects_ambiguous_or_invalid_password_configuration(
    repository: SQLiteUserRepository,
) -> None:
    service = AuthService(repository)

    with pytest.raises(AdminBootstrapError, match="只能配置一种"):
        service.ensure_bootstrap_admin(
            "course2career_admin",
            "unique-admin-pass-123",
            password_hash=hash_password("unique-admin-pass-123"),
        )
    with pytest.raises(AdminBootstrapError, match="哈希格式无效"):
        service.ensure_bootstrap_admin(
            "course2career_admin",
            password_hash="not-a-valid-password-hash",
        )
    with pytest.raises(AdminBootstrapError, match="哈希格式无效"):
        service.ensure_bootstrap_admin(
            "course2career_admin",
            password_hash="scrypt$invalid$8$1$00$00",
        )
