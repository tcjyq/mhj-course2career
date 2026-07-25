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


class AdminBootstrapError(ValueError):
    """首个管理员的安全初始化配置无效。"""


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

    def ensure_bootstrap_admin(self, username: str, password: str) -> Principal:
        """幂等创建初始管理员，且绝不提升已存在的普通账户。"""

        cleaned_username = username.strip()
        if not USERNAME_PATTERN.fullmatch(cleaned_username):
            raise AdminBootstrapError(
                "管理员用户名需要 3 到 32 个字符，只能包含字母、数字、下划线或连字符。"
            )
        if len(password) < 12:
            raise AdminBootstrapError("管理员密码至少需要 12 个字符。")
        if len(password) > 128:
            raise AdminBootstrapError("管理员密码不能超过 128 个字符。")

        normalized_username = cleaned_username.casefold()
        existing_user = self.repository.find_by_normalized_username(normalized_username)
        if existing_user is not None:
            return _existing_admin_or_raise(existing_user)

        user = StoredUser(
            id=str(uuid4()),
            username=cleaned_username,
            username_normalized=normalized_username,
            password_hash=hash_password(password),
            role=Role.ADMIN,
            plan=Plan.ADMIN,
            created_time=datetime.now(UTC).isoformat(),
        )
        try:
            self.repository.add(user)
        except sqlite3.IntegrityError as exc:
            existing_user = self.repository.find_by_normalized_username(
                normalized_username
            )
            if existing_user is None:
                raise AdminBootstrapError("管理员初始化失败。") from exc
            return _existing_admin_or_raise(existing_user)
        return _to_principal(user)


def _existing_admin_or_raise(user: StoredUser) -> Principal:
    if user.role != Role.ADMIN or user.plan != Plan.ADMIN:
        raise AdminBootstrapError(
            "管理员用户名已被普通账户占用，请在 Secrets 中更换用户名。"
        )
    return _to_principal(user)


def _to_principal(user: StoredUser) -> Principal:
    return Principal(
        user_id=user.id,
        username=user.username,
        role=user.role,
        plan=user.plan,
    )
