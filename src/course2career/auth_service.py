import re
import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from course2career.password_security import (
    hash_password,
    is_supported_password_hash,
    verify_password,
)
from course2career.permissions import Plan, Principal, Role
from course2career.user_repository import SQLiteUserRepository, StoredUser

USERNAME_PATTERN = re.compile(r"^[\w-]{3,32}$", flags=re.UNICODE)


class RegistrationError(ValueError):
    """公开注册信息不符合要求。"""


class InvalidCredentialsError(ValueError):
    """登录凭证无效；不区分用户名或密码错误。"""


class TooManyLoginAttemptsError(InvalidCredentialsError):
    """同一浏览器会话中的登录失败次数过多。"""


class InvalidSessionError(ValueError):
    """登录会话已失效，需要重新认证。"""


class AdminBootstrapError(ValueError):
    """首个管理员的安全初始化配置无效。"""


class AuthService:
    """注册和认证应用服务；公开注册只能创建普通用户。"""

    MAX_FAILED_LOGINS = 5
    LOGIN_WINDOW = timedelta(minutes=15)

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

    def authenticate(
        self,
        username: str,
        password: str,
        *,
        attempt_scope: str | None = None,
        now: datetime | None = None,
    ) -> Principal:
        normalized_username = username.strip().casefold()
        attempted_time = now or datetime.now(UTC)
        if (
            attempt_scope
            and self.repository.count_recent_failed_logins(
                attempt_scope,
                normalized_username,
                attempted_time - self.LOGIN_WINDOW,
            )
            >= self.MAX_FAILED_LOGINS
        ):
            raise TooManyLoginAttemptsError("登录尝试次数过多，请稍后再试。")

        user = self.repository.find_by_normalized_username(normalized_username)
        if (
            user is None
            or getattr(user, "status", "active") != "active"
            or not verify_password(password, user.password_hash)
        ):
            if attempt_scope:
                self.repository.record_failed_login(
                    attempt_scope,
                    normalized_username,
                    attempted_time,
                )
            raise InvalidCredentialsError("用户名或密码错误。")
        if attempt_scope:
            self.repository.clear_failed_logins(attempt_scope, normalized_username)
        return _to_principal(user)

    def refresh_principal(self, principal: Principal) -> Principal:
        if principal.user_id is None or principal.session_version is None:
            raise InvalidSessionError("登录状态已失效，请重新登录。")
        user = self.repository.find_by_id(principal.user_id)
        if (
            user is None
            or getattr(user, "status", "active") != "active"
            or getattr(user, "session_version", 1) != principal.session_version
        ):
            raise InvalidSessionError("登录状态已失效，请重新登录。")
        return _to_principal(user)

    def ensure_bootstrap_admin(
        self,
        username: str,
        password: str | None = None,
        *,
        password_hash: str | None = None,
    ) -> Principal:
        """幂等创建初始管理员，且绝不提升已存在的普通账户。"""

        cleaned_username = username.strip()
        if not USERNAME_PATTERN.fullmatch(cleaned_username):
            raise AdminBootstrapError(
                "管理员用户名需要 3 到 32 个字符，只能包含字母、数字、下划线或连字符。"
            )
        find_admin = getattr(self.repository, "find_admin", None)
        existing_admin = find_admin() if callable(find_admin) else None
        if existing_admin is not None:
            if existing_admin.username_normalized == cleaned_username.casefold():
                if (
                    password is not None
                    and password_hash is None
                    and verify_password(password, existing_admin.password_hash)
                ):
                    return _to_principal(existing_admin)
                encoded_password = _resolve_admin_password_hash(
                    password,
                    password_hash,
                )
                if encoded_password != existing_admin.password_hash:
                    rotated_admin = self.repository.update_password_hash(
                        existing_admin.id,
                        encoded_password,
                    )
                    if rotated_admin is None:
                        raise AdminBootstrapError("管理员密码轮换失败。")
                    return _to_principal(rotated_admin)
            return _to_principal(existing_admin)

        normalized_username = cleaned_username.casefold()
        existing_user = self.repository.find_by_normalized_username(normalized_username)
        if existing_user is not None:
            return _existing_admin_or_raise(existing_user)

        encoded_password = _resolve_admin_password_hash(password, password_hash)
        user = StoredUser(
            id=str(uuid4()),
            username=cleaned_username,
            username_normalized=normalized_username,
            password_hash=encoded_password,
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


def _resolve_admin_password_hash(
    password: str | None,
    password_hash: str | None,
) -> str:
    if password and password_hash:
        raise AdminBootstrapError("管理员密码和密码哈希只能配置一种。")
    if password_hash:
        if not is_supported_password_hash(password_hash):
            raise AdminBootstrapError("管理员密码哈希格式无效。")
        return password_hash
    if password is None:
        raise AdminBootstrapError("管理员密码配置不完整。")
    if len(password) < 12:
        raise AdminBootstrapError("管理员密码至少需要 12 个字符。")
    if len(password) > 128:
        raise AdminBootstrapError("管理员密码不能超过 128 个字符。")
    return hash_password(password)


def _to_principal(user: StoredUser) -> Principal:
    return Principal(
        user_id=user.id,
        username=user.username,
        role=user.role,
        plan=user.plan,
        session_version=getattr(user, "session_version", 1),
    )
