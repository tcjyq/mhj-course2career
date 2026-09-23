"""自带 Key 开关与每次敏感操作前的持久化权限复核。"""

from datetime import UTC, datetime

from course2career.permissions import (
    Permission,
    PermissionDeniedError,
    Plan,
    Principal,
    Role,
    authorize,
)
from course2career.product_repository import SQLiteProductRepository, StoredBYOKMode


def is_legacy_byok_principal(principal: Principal) -> bool:
    return (
        principal.role in {Role.ADMIN, Role.DEVELOPER}
        or principal.plan == Plan.DEVELOPER
    )


def require_current_byok_access(
    principal: Principal, repository: SQLiteProductRepository
) -> None:
    """关闭开关后旧会话也立即失去读取、写入和调用能力。"""
    authorize(principal, Permission.USE_OWN_API_KEY)
    if principal.user_id is None:
        raise PermissionDeniedError("登录后才能使用自己的 API Key。")
    if is_legacy_byok_principal(principal):
        return
    mode = repository.get_byok_mode(principal.user_id)
    if mode is None or not mode.byok_enabled:
        raise PermissionDeniedError("请先启用开发者模式。")


class BYOKModeService:
    def __init__(self, repository: SQLiteProductRepository) -> None:
        self.repository = repository

    def is_enabled(self, principal: Principal) -> bool:
        if principal.role == Role.GUEST or principal.user_id is None:
            return False
        if is_legacy_byok_principal(principal):
            return True
        mode = self.repository.get_byok_mode(principal.user_id)
        return mode is not None and mode.byok_enabled

    def set_enabled(self, principal: Principal, enabled: bool) -> StoredBYOKMode:
        if principal.role == Role.GUEST or principal.user_id is None:
            raise PermissionDeniedError("请先登录。")
        if is_legacy_byok_principal(principal):
            raise PermissionDeniedError("历史开发者及管理员无需切换开发者模式。")
        return self.repository.set_byok_mode(
            principal.user_id,
            enabled,
            datetime.now(UTC).isoformat(),
        )
