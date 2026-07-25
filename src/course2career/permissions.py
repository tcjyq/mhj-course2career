from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    GUEST = "guest"
    USER = "user"
    DEVELOPER = "developer"
    ADMIN = "admin"


class Plan(StrEnum):
    FREE = "free"
    PRO = "pro"
    DEVELOPER = "developer"
    ADMIN = "admin"


class Permission(StrEnum):
    USE_DEMO = "demo:use"
    USE_SYSTEM_AI = "ai:use_system"
    SAVE_ANALYSIS = "analysis:save"
    VIEW_OWN_ANALYSES = "analysis:view_own"
    CONFIGURE_OWN_API_KEY = "api_key:configure_own"
    USE_OWN_API_KEY = "ai:use_own_key"
    VIEW_ADVANCED_REPORT = "report:view_advanced"
    VIEW_SYSTEM_STATUS = "system:view_status"
    MANAGE_SYSTEM_CONFIG = "system:manage_config"
    MANAGE_MEMBERSHIPS = "membership:manage"


class Principal(BaseModel):
    """当前请求的已认证主体；游客没有持久用户 ID。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Role = Role.GUEST
    plan: Plan = Plan.FREE
    user_id: str | None = None
    username: str | None = None


class PermissionDeniedError(PermissionError):
    """当前主体没有执行目标操作的权限。"""


ROLE_PERMISSIONS = {
    Role.GUEST: frozenset({Permission.USE_DEMO, Permission.USE_SYSTEM_AI}),
    Role.USER: frozenset(
        {
            Permission.USE_DEMO,
            Permission.USE_SYSTEM_AI,
            Permission.SAVE_ANALYSIS,
            Permission.VIEW_OWN_ANALYSES,
            Permission.VIEW_ADVANCED_REPORT,
        }
    ),
    Role.DEVELOPER: frozenset(
        {
            Permission.USE_DEMO,
            Permission.USE_SYSTEM_AI,
            Permission.SAVE_ANALYSIS,
            Permission.VIEW_OWN_ANALYSES,
            Permission.CONFIGURE_OWN_API_KEY,
            Permission.USE_OWN_API_KEY,
            Permission.VIEW_ADVANCED_REPORT,
        }
    ),
    Role.ADMIN: frozenset(Permission),
}

PLAN_PERMISSIONS = {
    Plan.FREE: frozenset(
        {
            Permission.USE_DEMO,
            Permission.USE_SYSTEM_AI,
            Permission.SAVE_ANALYSIS,
            Permission.VIEW_OWN_ANALYSES,
        }
    ),
    Plan.PRO: frozenset(
        {
            Permission.USE_DEMO,
            Permission.USE_SYSTEM_AI,
            Permission.SAVE_ANALYSIS,
            Permission.VIEW_OWN_ANALYSES,
            Permission.VIEW_ADVANCED_REPORT,
        }
    ),
    Plan.DEVELOPER: frozenset(
        {
            Permission.USE_DEMO,
            Permission.USE_SYSTEM_AI,
            Permission.SAVE_ANALYSIS,
            Permission.VIEW_OWN_ANALYSES,
            Permission.VIEW_ADVANCED_REPORT,
            Permission.CONFIGURE_OWN_API_KEY,
            Permission.USE_OWN_API_KEY,
        }
    ),
    Plan.ADMIN: frozenset(Permission),
}

PLAN_SYSTEM_AI_DAILY_LIMITS = {
    Plan.FREE: 5,
    Plan.PRO: 20,
    Plan.DEVELOPER: 20,
    Plan.ADMIN: None,
}


def authorize(principal: Principal, permission: Permission) -> None:
    """在业务动作前同时执行服务端角色和套餐权限判断。"""

    if (
        permission not in ROLE_PERMISSIONS[principal.role]
        or permission not in PLAN_PERMISSIONS[principal.plan]
    ):
        raise PermissionDeniedError("当前用户没有执行此操作的权限。")


def daily_ai_limit(principal: Principal, key_mode: str) -> int | None:
    """返回AI日调用上限；None表示不由平台额度限制。"""

    if key_mode == "user":
        authorize(principal, Permission.USE_OWN_API_KEY)
        return None
    if key_mode != "system":
        raise ValueError("不支持的 API Key 模式。")
    authorize(principal, Permission.USE_SYSTEM_AI)
    if principal.role == Role.GUEST:
        return 2
    if principal.role == Role.ADMIN and principal.plan == Plan.ADMIN:
        return None
    if principal.plan == Plan.ADMIN:
        raise PermissionDeniedError("管理员套餐只能由管理员角色使用。")
    return PLAN_SYSTEM_AI_DAILY_LIMITS[principal.plan]
