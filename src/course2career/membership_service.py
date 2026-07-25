from pydantic import BaseModel, ConfigDict

from course2career.permissions import (
    Permission,
    Plan,
    Principal,
    Role,
    authorize,
)
from course2career.user_repository import SQLiteUserRepository


class UserNotFoundError(LookupError):
    """套餐变更的目标用户不存在。"""


class MembershipChangeError(ValueError):
    """套餐变更会破坏当前管理会话的安全边界。"""


class Membership(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    role: Role
    plan: Plan


PLAN_ROLES = {
    Plan.FREE: Role.USER,
    Plan.PRO: Role.USER,
    Plan.DEVELOPER: Role.DEVELOPER,
    Plan.ADMIN: Role.ADMIN,
}


class MembershipService:
    """支付无关的套餐生效入口；当前仅允许管理员调用。"""

    def __init__(self, repository: SQLiteUserRepository) -> None:
        self.repository = repository

    def change_plan(
        self,
        actor: Principal,
        user_id: str,
        target_plan: Plan,
    ) -> Membership:
        authorize(actor, Permission.MANAGE_MEMBERSHIPS)
        if actor.user_id == user_id and target_plan != Plan.ADMIN:
            raise MembershipChangeError("不能在当前会话中取消自己的管理员权限。")
        role = PLAN_ROLES[target_plan]
        if not self.repository.update_membership(user_id, role, target_plan):
            raise UserNotFoundError("目标用户不存在。")
        return Membership(user_id=user_id, role=role, plan=target_plan)
