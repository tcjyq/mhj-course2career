"""Synthetic users for tests; never imported by the application."""

from datetime import UTC, datetime
from uuid import uuid4

from course2career.auth_service import AuthService
from course2career.password_security import hash_password
from course2career.permissions import Plan, Principal, Role
from course2career.user_repository import SQLiteUserRepository, StoredUser


def seed_user(
    repository: SQLiteUserRepository, username: str, password: str
) -> Principal:
    repository.add(
        StoredUser(
            id=str(uuid4()),
            username=username,
            username_normalized=username.casefold(),
            password_hash=hash_password(password),
            role=Role.USER,
            plan=Plan.FREE,
            created_time=datetime.now(UTC).isoformat(),
        )
    )
    return AuthService(repository).authenticate(username, password)
