import sqlite3
from pathlib import Path

import pytest

from course2career.membership_service import (
    MembershipChangeError,
    MembershipService,
    UserNotFoundError,
)
from course2career.permissions import (
    PermissionDeniedError,
    Plan,
    Principal,
    Role,
)
from course2career.product_repository import SQLiteProductRepository
from course2career.user_repository import StoredUser


def _add_user(
    repository: SQLiteProductRepository,
    *,
    user_id: str,
    role: Role = Role.USER,
    plan: Plan = Plan.FREE,
) -> None:
    repository.add(
        StoredUser(
            id=user_id,
            username=user_id,
            username_normalized=user_id,
            password_hash="not-used",
            role=role,
            plan=plan,
            created_time="2026-07-25T00:00:00+00:00",
        )
    )


def test_admin_can_assign_pro_and_developer_plans(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "test.db")
    _add_user(repository, user_id="user-1")
    service = MembershipService(repository)
    admin = Principal(
        role=Role.ADMIN,
        plan=Plan.ADMIN,
        user_id="admin-1",
        username="admin",
    )

    pro_membership = service.change_plan(admin, "user-1", Plan.PRO)
    developer_membership = service.change_plan(admin, "user-1", Plan.DEVELOPER)

    assert pro_membership.role == Role.USER
    assert pro_membership.plan == Plan.PRO
    assert developer_membership.role == Role.DEVELOPER
    assert developer_membership.plan == Plan.DEVELOPER
    stored = repository.find_by_id("user-1")
    assert stored is not None
    assert stored.role == Role.DEVELOPER
    assert stored.plan == Plan.DEVELOPER


def test_non_admin_cannot_change_membership(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "test.db")
    _add_user(repository, user_id="user-1")
    service = MembershipService(repository)

    with pytest.raises(PermissionDeniedError):
        service.change_plan(
            Principal(
                role=Role.USER,
                plan=Plan.PRO,
                user_id="user-1",
                username="user-1",
            ),
            "user-1",
            Plan.DEVELOPER,
        )


def test_change_plan_rejects_unknown_user(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "test.db")
    service = MembershipService(repository)
    admin = Principal(role=Role.ADMIN, plan=Plan.ADMIN)

    with pytest.raises(UserNotFoundError):
        service.change_plan(admin, "missing", Plan.PRO)


def test_admin_cannot_remove_own_admin_plan(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "test.db")
    _add_user(
        repository,
        user_id="admin-1",
        role=Role.ADMIN,
        plan=Plan.ADMIN,
    )
    service = MembershipService(repository)
    admin = Principal(
        role=Role.ADMIN,
        plan=Plan.ADMIN,
        user_id="admin-1",
        username="admin-1",
    )

    with pytest.raises(MembershipChangeError):
        service.change_plan(admin, "admin-1", Plan.FREE)


def test_admin_cannot_grant_owner_admin_plan_to_another_user(
    tmp_path: Path,
) -> None:
    repository = SQLiteProductRepository(tmp_path / "test.db")
    _add_user(repository, user_id="user-1")
    service = MembershipService(repository)
    admin = Principal(
        role=Role.ADMIN,
        plan=Plan.ADMIN,
        user_id="admin-1",
        username="admin-1",
    )

    with pytest.raises(MembershipChangeError, match="所有者"):
        service.change_plan(admin, "user-1", Plan.ADMIN)


def test_repository_migrates_legacy_privileged_plans(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                username_normalized TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                created_time TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO users VALUES (
                'developer-1', 'developer', 'developer',
                'not-used', 'developer', 'free', '2026-07-23T00:00:00+00:00'
            )
            """
        )

    repository = SQLiteProductRepository(database_path)

    migrated = repository.find_by_id("developer-1")
    assert migrated is not None
    assert migrated.plan == Plan.DEVELOPER
