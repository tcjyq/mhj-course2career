"""Developer Mode 的权限、迁移和 UI 回归；不连接模型供应商。"""

import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from course2career.access_services import AIUsageService
from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.key_encryption import APIKeyCipher
from course2career.llm_provider import ProviderName
from course2career.permissions import (
    Permission,
    PermissionDeniedError,
    Plan,
    Principal,
    Role,
    authorize,
    daily_ai_limit,
)
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_profile import ProviderProfileService
from course2career.user_repository import StoredUser


def _user(
    repository: SQLiteProductRepository,
    user_id: str,
    *,
    role: Role = Role.USER,
    plan: Plan = Plan.FREE,
) -> Principal:
    repository.add(
        StoredUser(
            id=user_id,
            username=user_id,
            username_normalized=user_id,
            password_hash="unused-test-hash",
            role=role,
            plan=plan,
            created_time="2026-09-23T00:00:00+00:00",
        )
    )
    return Principal(role=role, plan=plan, user_id=user_id, session_version=1)


def test_guest_denied_and_user_self_service_keeps_free_quota(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "free.db")
    modes = BYOKModeService(repository)
    guest = Principal()
    with pytest.raises(PermissionDeniedError):
        modes.set_enabled(guest, True)
    user = _user(repository, "free-user")
    with pytest.raises(PermissionDeniedError):
        authorize(user, Permission.CONFIGURE_OWN_API_KEY)
    enabled = modes.set_enabled(user, True)
    assert enabled.byok_enabled
    assert enabled.user_id == user.user_id and enabled.updated_at
    assert modes.is_enabled(user)
    fresh = AuthService(repository).refresh_principal(user)
    assert fresh.byok_enabled
    authorize(fresh, Permission.CONFIGURE_OWN_API_KEY)
    assert daily_ai_limit(fresh, "system") == 5
    assert daily_ai_limit(fresh, "user") is None
    stored = repository.find_by_id("free-user")
    assert stored is not None
    assert (stored.role, stored.plan) == (Role.USER, Plan.FREE)


def test_pro_quota_independent_from_byok(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "pro.db")
    pro = _user(repository, "pro-user", plan=Plan.PRO)
    modes = BYOKModeService(repository)
    modes.set_enabled(pro, True)
    enabled = AuthService(repository).refresh_principal(pro)
    assert daily_ai_limit(enabled, "system") == 20
    assert daily_ai_limit(enabled, "user") is None
    usage = AIUsageService(repository)
    usage.start_call(enabled, "user", "test-model", provider="openai")
    assert usage.get_quota_status(enabled, "system").used == 0
    assert repository.find_by_id("pro-user").plan == Plan.PRO


def test_disable_blocks_stale_session_and_reenable_preserves_ciphertext(
    tmp_path: Path,
) -> None:
    repository = SQLiteProductRepository(tmp_path / "keys.db")
    user = _user(repository, "owner")
    modes = BYOKModeService(repository)
    modes.set_enabled(user, True)
    enabled = AuthService(repository).refresh_principal(user)
    keys = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
    profiles = ProviderProfileService(repository)
    keys.save_key(enabled, ProviderName.OPENAI, "fake-owned-key-123")
    profiles.save(enabled, ProviderName.OPENAI, "global", "gpt-5.6-luna")
    before = repository.get_api_key("owner", "openai")
    assert before is not None
    modes.set_enabled(enabled, False)
    assert not AuthService(repository).refresh_principal(enabled).byok_enabled
    assert not modes.is_enabled(enabled)
    for action in (
        lambda: keys.save_key(enabled, ProviderName.OPENAI, "fake-new-key-456"),
        lambda: keys.get_key(enabled, ProviderName.OPENAI),
        lambda: keys.list_keys(enabled),
        lambda: keys.delete_key(enabled, ProviderName.OPENAI),
        lambda: profiles.get(enabled, ProviderName.OPENAI),
        lambda: profiles.list(enabled),
        lambda: profiles.delete(enabled, ProviderName.OPENAI),
        lambda: AIUsageService(repository).start_call(enabled, "user", "gpt-5.6-luna"),
    ):
        with pytest.raises(PermissionDeniedError):
            action()
    assert repository.get_api_key("owner", "openai") == before
    modes.set_enabled(enabled, True)
    restored = AuthService(repository).refresh_principal(enabled)
    assert keys.get_key(restored, ProviderName.OPENAI) == "fake-owned-key-123"
    assert profiles.get(restored, ProviderName.OPENAI).model_id == "gpt-5.6-luna"
    assert repository.get_api_key("owner", "openai") == before


def test_cross_user_isolation_and_legacy_access(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "legacy.db")
    alice = _user(repository, "alice")
    bob = _user(repository, "bob")
    legacy_role = _user(repository, "legacy-role", role=Role.DEVELOPER)
    legacy_plan = _user(repository, "legacy-plan", plan=Plan.DEVELOPER)
    admin = _user(repository, "admin", role=Role.ADMIN, plan=Plan.ADMIN)
    modes = BYOKModeService(repository)
    keys = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
    modes.set_enabled(alice, True)
    modes.set_enabled(bob, True)
    enabled_alice = AuthService(repository).refresh_principal(alice)
    enabled_bob = AuthService(repository).refresh_principal(bob)
    keys.save_key(enabled_alice, ProviderName.GEMINI, "fake-alice-key-1")
    keys.save_key(enabled_bob, ProviderName.GEMINI, "fake-bob-key-222")
    assert keys.get_key(enabled_alice, ProviderName.GEMINI) == "fake-alice-key-1"
    assert keys.get_key(enabled_bob, ProviderName.GEMINI) == "fake-bob-key-222"
    keys.delete_key(enabled_alice, ProviderName.GEMINI)
    assert keys.get_key(enabled_bob, ProviderName.GEMINI) == "fake-bob-key-222"
    for principal in (legacy_role, legacy_plan, admin):
        assert modes.is_enabled(principal)
        authorize(principal, Permission.USE_OWN_API_KEY)
        keys.save_key(principal, ProviderName.OPENAI, "fake-legacy-key-1")


def test_migration_idempotent_and_failed_update_rolls_back(tmp_path: Path) -> None:
    path = tmp_path / "older.db"
    repository = SQLiteProductRepository(path)
    user = _user(repository, "owner")
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE user_byok_settings")
    migrated = SQLiteProductRepository(path)
    assert migrated.get_byok_mode("owner") is None
    modes = BYOKModeService(migrated)
    modes.set_enabled(user, True)
    reopened = SQLiteProductRepository(path)
    assert reopened.get_byok_mode("owner").byok_enabled
    with pytest.raises(LookupError):
        reopened.set_byok_mode("missing", False, "2026-09-23T00:00:00+00:00")
    assert reopened.get_byok_mode("owner").byok_enabled


def test_developer_and_membership_pages_show_self_service(tmp_path: Path) -> None:
    path = (tmp_path / "ui.db").as_posix()
    repository = SQLiteProductRepository(path)
    user = _user(repository, "ui-user")
    source = f'''
import streamlit as st
from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.key_encryption import APIKeyCipher
from course2career.permissions import Principal, Role, Plan
from course2career.product_repository import SQLiteProductRepository
from course2career.ui.developer_page import render_developer_page
repository = SQLiteProductRepository(r"{path}")
auth = AuthService(repository)
if "principal" not in st.session_state:
    st.session_state.principal = Principal(
        role=Role.USER, plan=Plan.FREE, user_id="ui-user", session_version=1
    )
principal = auth.refresh_principal(st.session_state.principal)
st.session_state.principal = principal
keys = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
render_developer_page(
    principal, keys, None, byok_mode_service=BYOKModeService(repository)
)
'''
    app = AppTest.from_string(source).run()
    assert not app.exception
    assert app.title[0].value == "开发者模式"
    assert len(app.selectbox) == 0
    next(
        button for button in app.button if button.label == "启用开发者模式"
    ).click().run()
    assert not app.exception
    assert app.title[0].value == "我的 AI Provider"
    assert len([box for box in app.selectbox if box.label == "官方端点"]) == 10
    assert repository.get_byok_mode(user.user_id).byok_enabled
    next(
        button for button in app.button if button.label == "关闭开发者模式"
    ).click().run()
    assert not app.exception
    assert app.title[0].value == "开发者模式"
    assert not repository.get_byok_mode(user.user_id).byok_enabled
