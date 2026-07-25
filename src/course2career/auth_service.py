import re
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from course2career.password_security import hash_password, verify_password
from course2career.permissions import Plan, Principal, Role
from course2career.user_repository import SQLiteUserRepository, StoredUser

USERNAME_PATTERN = re.compile(r"^[\w-]{3,32}$", flags=re.UNICODE)


class RegistrationError(ValueError):
    """公开注册信息不符合要求。"""


class InvalidCredentialsError(ValueError):
    """登录凭证无效；不区分用户名或密码错误。"""


class AuthService:
    """注册和认证应用服务；公开注册只能创建普通用户。"""

    def __init__(self, repository: SQLiteUserRepository) -> None:
        self.repository = repository

    def register(self, username: str, password: str) -> Principal:
        cleaned_username = username.strip()
        if not USERNAME_PATTERN.fullmatch(cleaned_username):
            raise RegistrationError(
                "用户名需要 3 到 32 个字符，只能包含字母、数字、下划线或连字符。"
            )
        if len(password) < 8:
            raise RegistrationError("密码至少需要 8 个字符。")
        if len(password) > 128:
            raise RegistrationError("密码不能超过 128 个字符。")

        user = StoredUser(
            id=str(uuid4()),
            username=cleaned_username,
            username_normalized=cleaned_username.casefold(),
            password_hash=hash_password(password),
            role=Role.USER,
            plan=Plan.FREE,
            created_time=datetime.now(UTC).isoformat(),
        )
        try:
            self.repository.add(user)
        except sqlite3.IntegrityError as exc:
            raise RegistrationError("该用户名已存在。") from exc
        return _to_principal(user)

    def authenticate(self, username: str, password: str) -> Principal:
        user = self.repository.find_by_normalized_username(username.strip().casefold())
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("用户名或密码错误。")
        return _to_principal(user)


def _to_principal(user: StoredUser) -> Principal:
    return Principal(
        user_id=user.id,
        username=user.username,
        role=user.role,
        plan=user.plan,
    )
