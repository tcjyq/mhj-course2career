import pytest

from course2career.permissions import (
    Permission,
    PermissionDeniedError,
    Plan,
    Principal,
    Role,
    authorize,
    daily_ai_limit,
)


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.GUEST, Permission.USE_DEMO, True),
        (Role.GUEST, Permission.SAVE_ANALYSIS, False),
        (Role.USER, Permission.SAVE_ANALYSIS, True),
        (Role.USER, Permission.CONFIGURE_OWN_API_KEY, False),
        (Role.DEVELOPER, Permission.CONFIGURE_OWN_API_KEY, True),
        (Role.DEVELOPER, Permission.USE_OWN_API_KEY, True),
        (Role.ADMIN, Permission.VIEW_SYSTEM_STATUS, True),
        (Role.ADMIN, Permission.MANAGE_SYSTEM_CONFIG, True),
        (Role.USER, Permission.VIEW_SYSTEM_STATUS, False),
        (Role.USER, Permission.MANAGE_SYSTEM_CONFIG, False),
    ],
)
def test_role_permissions_are_explicit(
    role: Role, permission: Permission, allowed: bool
) -> None:
    plan = {
        Role.GUEST: Plan.FREE,
        Role.USER: Plan.FREE,
        Role.DEVELOPER: Plan.DEVELOPER,
        Role.ADMIN: Plan.ADMIN,
    }[role]
    principal = Principal(role=role, plan=plan)

    if allowed:
        authorize(principal, permission)
    else:
        with pytest.raises(PermissionDeniedError):
            authorize(principal, permission)


def test_plan_capabilities_and_ai_limits() -> None:
    guest = Principal(role=Role.GUEST, plan=Plan.FREE)
    free = Principal(role=Role.USER, plan=Plan.FREE)
    pro = Principal(role=Role.USER, plan=Plan.PRO)
    developer = Principal(role=Role.DEVELOPER, plan=Plan.DEVELOPER)
    admin = Principal(role=Role.ADMIN, plan=Plan.ADMIN)

    assert daily_ai_limit(guest, key_mode="system") == 2
    assert daily_ai_limit(free, key_mode="system") == 5
    assert daily_ai_limit(pro, key_mode="system") == 20
    assert daily_ai_limit(developer, key_mode="system") == 20
    assert daily_ai_limit(developer, key_mode="user") is None
    assert daily_ai_limit(admin, key_mode="system") is None

    with pytest.raises(PermissionDeniedError):
        authorize(free, Permission.VIEW_ADVANCED_REPORT)
    authorize(pro, Permission.VIEW_ADVANCED_REPORT)
    authorize(developer, Permission.USE_OWN_API_KEY)


def test_plan_cannot_cross_role_security_boundary() -> None:
    inconsistent = Principal(role=Role.USER, plan=Plan.DEVELOPER)

    with pytest.raises(PermissionDeniedError):
        authorize(inconsistent, Permission.USE_OWN_API_KEY)
