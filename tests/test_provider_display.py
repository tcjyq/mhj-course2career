"""Display reuse cannot authorize Secrets or survive the render/identity boundary."""

import time
from unittest.mock import Mock

import pytest

from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService, InvalidSessionError
from course2career.byok_mode import BYOKModeService
from course2career.config import Settings
from course2career.key_encryption import APIKeyCipher
from course2career.llm_provider import ProviderName
from course2career.model_discovery import CatalogSnapshot, ModelCatalogService
from course2career.permissions import PermissionDeniedError, Principal
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_display import provider_display_view
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_profile import ProviderProfileService
from course2career.provider_registry import get_provider_preset


@pytest.fixture
def account(tmp_path):
    repo = SQLiteProductRepository(tmp_path / "display.db")
    auth = AuthService(repo)
    principal = auth.register("display_a", "synthetic-password-123")
    mode = BYOKModeService(repo)
    mode.set_enabled(principal, True)
    principal = auth.refresh_principal(principal)
    keys = APIKeyService(repo, APIKeyCipher(bytes(range(32))))
    profiles = ProviderProfileService(repo)
    keys.save_key(principal, ProviderName.OPENAI, "synthetic-display-key")
    profiles.save(principal, ProviderName.OPENAI, "global", "synthetic-model")
    return repo, auth, mode, principal, keys, profiles


def _prime(catalog, principal):
    key = catalog._cache_key(
        principal, get_provider_preset(ProviderName.OPENAI), "global", None
    )
    catalog._cache[key] = (
        CatalogSnapshot(ProviderName.OPENAI, "global", (), "synthetic-time"),
        time.monotonic(),
    )


def test_one_render_reads_once_then_display_lookup_has_no_db(account, monkeypatch):
    repo, _, _, principal, keys, profiles = account
    catalog = ModelCatalogService(keys)
    _prime(catalog, principal)
    connect = Mock(wraps=repo._connect)
    monkeypatch.setattr(repo, "_connect", connect)
    with provider_display_view(principal, keys, profiles) as view:
        assert connect.call_count == 3  # mode, all Key metadata, all profiles
        monkeypatch.setattr(repo, "_connect", Mock(side_effect=AssertionError("DB")))
        for _ in range(10):
            assert (
                catalog.peek(
                    principal, ProviderName.OPENAI, "global", display_view=view
                )
                is not None
            )
            catalog.selected_model(
                principal,
                ProviderName.OPENAI,
                "global",
                "synthetic-model",
                display_view=view,
            )
        assert not hasattr(view.keys[ProviderName.OPENAI], "encrypted_key")
        assert not hasattr(view.keys[ProviderName.OPENAI], "nonce")
    with pytest.raises(PermissionDeniedError):
        catalog.peek(principal, ProviderName.OPENAI, "global", display_view=view)


def test_view_rejects_other_account_guest_and_changed_principal(account):
    _, auth, _, principal, keys, profiles = account
    other = auth.register("display_b", "synthetic-password-123")
    catalog = ModelCatalogService(keys)
    with provider_display_view(principal, keys, profiles) as view:
        for denied in (
            other,
            Principal(),
            principal.model_copy(update={"byok_enabled": False}),
        ):
            with pytest.raises(PermissionDeniedError):
                catalog.peek(denied, ProviderName.OPENAI, "global", display_view=view)
    with provider_display_view(other, keys, profiles) as other_view:
        assert other_view is None


@pytest.mark.parametrize("change", ["rotate", "delete"])
def test_key_version_invalidates_catalog_on_next_render(account, change):
    _, _, _, principal, keys, profiles = account
    catalog = ModelCatalogService(keys)
    _prime(catalog, principal)
    with provider_display_view(principal, keys, profiles) as view:
        assert catalog.peek(principal, ProviderName.OPENAI, "global", display_view=view)
    if change == "rotate":
        keys.save_key(principal, ProviderName.OPENAI, "synthetic-rotated-key")
    else:
        keys.delete_key(principal, ProviderName.OPENAI)
    with provider_display_view(principal, keys, profiles) as view:
        assert (
            catalog.peek(principal, ProviderName.OPENAI, "global", display_view=view)
            is None
        )


def test_disable_blocks_sensitive_actions_even_while_display_view_is_live(account):
    _, _, mode, principal, keys, profiles = account
    factory = LLMProviderFactory(Settings(), keys)
    catalog = ModelCatalogService(keys, getter=Mock(side_effect=AssertionError("HTTP")))
    with provider_display_view(principal, keys, profiles) as view:
        assert view is not None
        mode.set_enabled(principal, False)
        for action in (
            lambda: keys.get_key(principal, ProviderName.OPENAI),
            lambda: keys.save_key(principal, ProviderName.OPENAI, "synthetic-new-key"),
            lambda: keys.delete_key(principal, ProviderName.OPENAI),
            lambda: profiles.save(principal, ProviderName.OPENAI, "global", "changed"),
            lambda: factory.create(
                principal,
                provider=ProviderName.OPENAI,
                key_mode="user",
                model="synthetic-model",
            ),
            lambda: catalog.discover_models(
                principal, ProviderName.OPENAI, "global", force_refresh=True
            ),
        ):
            with pytest.raises(PermissionDeniedError):
                action()
    with provider_display_view(principal, keys, profiles) as view:
        assert view is None


def test_revoke_rejects_next_render_before_display(account):
    _, auth, _, principal, keys, profiles = account
    token = auth.create_session(principal)
    with provider_display_view(principal, keys, profiles) as old_view:
        assert old_view is not None
    auth.revoke_session(token)
    with pytest.raises(InvalidSessionError):
        auth.refresh_session(principal, token)
    with pytest.raises(PermissionDeniedError):
        old_view.require_owner(principal)


def _developer_app(account, token=None):
    from streamlit.testing.v1 import AppTest

    repo, _, _, principal, _, _ = account
    app = AppTest.from_string(
        f"""
import streamlit as st
from course2career.api_key_service import APIKeyService
from course2career.byok_mode import BYOKModeService
from course2career.key_encryption import APIKeyCipher
from course2career.model_discovery import ModelCatalogService
from course2career.permissions import Principal
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_profile import ProviderProfileService
from course2career.ui.developer_page import render_developer_page
repo = SQLiteProductRepository({str(repo.database_path)!r})
keys = APIKeyService(repo, APIKeyCipher(bytes(range(32))))
st.session_state.auth_session_token = {token!r}
render_developer_page(
    Principal.model_validate_json({principal.model_dump_json()!r}), keys, None,
    ProviderProfileService(repo), byok_mode_service=BYOKModeService(repo),
    catalog_service=ModelCatalogService(keys),
)
"""
    ).run()
    return app


def test_all_ten_cards_render_with_real_catalog_service(account):
    app = _developer_app(account)
    assert not app.exception
    assert sum(button.label == "刷新模型" for button in app.button) == 10


def test_normal_developer_render_never_refreshes_or_decrypts(account, monkeypatch):
    import httpx

    from course2career.model_catalog import DeepSeekModelCatalog

    def forbidden(*_args, **_kwargs):
        pytest.fail("normal render attempted Provider HTTP or Secret use")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(DeepSeekModelCatalog, "refresh", forbidden)
    monkeypatch.setattr(APIKeyService, "get_key", forbidden)
    monkeypatch.setattr(LLMProviderFactory, "create", forbidden)
    app = _developer_app(account)
    assert not app.exception
    assert sum(button.label == "刷新模型" for button in app.button) == 10


@pytest.mark.parametrize("version", [0, 1])
def test_developer_verification_label_uses_actual_evidence_version(
    account, monkeypatch, version
):
    from dataclasses import replace

    import course2career.model_capability as capabilities
    import course2career.ui.developer_page as developer
    from course2career.provider_runtime import ModelAttempt, ModelMatch, ModelTrace
    from course2career.provider_verification import CERTIFIED_RECORD_PATH, load_records

    legacy = next(
        record
        for record in load_records(CERTIFIED_RECORD_PATH).values()
        if record.provider == ProviderName.DEEPSEEK
    )
    trace = ModelTrace(
        legacy.model,
        legacy.model,
        (
            ModelAttempt(
                legacy.model, legacy.model, success=True, response_received=True
            ),
        ),
    )
    record = (
        legacy
        if version == 0
        else replace(
            legacy,
            identity_evidence_version=1,
            model_match=ModelMatch.MATCH,
            model_traces=(trace,) * (legacy.fixture_count + 1),
            verified_at="2026-10-05T00:00:00+00:00",
        )
    )

    def lookup(provider, endpoint, model):
        return (
            record
            if (provider, endpoint, model)
            == (record.provider, record.endpoint_id, record.model)
            else None
        )

    monkeypatch.setattr(capabilities, "get_record", lookup)
    monkeypatch.setattr(developer, "get_record", lookup)
    app = _developer_app(account)
    assert not app.exception
    captions = "\n".join(item.value for item in app.caption)
    if version == 0:
        assert f"{legacy.verified_at[:10]} 旧记录的返回模型身份证据有限" in captions
        assert "实现认证（历史记录）" in captions
        assert "精确模型实现认证具有逐次身份" not in captions
    else:
        assert "旧记录的返回模型身份证据有限" not in captions
        assert "精确模型实现认证具有逐次身份与固定集证据" in captions
        assert "✓ Course2Career 精确模型实现认证" in captions
    assert legacy.legacy_model_identity_evidence


def test_revoked_session_cannot_save_from_prior_render_callback(account):
    _, auth, _, principal, _, profiles = account
    token = auth.create_session(principal)
    app = _developer_app(account, token)
    before = profiles.get(principal, ProviderName.OPENAI)
    auth.revoke_session(token)
    saves = [button for button in app.button if button.label == "保存配置"]
    saves[6].click().run()
    assert not app.exception
    assert any("登录状态已失效" in item.value for item in app.info)
    assert profiles.get(principal, ProviderName.OPENAI) == before
