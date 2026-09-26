"""C08-C 官方目录映射、隔离与权限；网络响应均为本地合成数据。"""

import sqlite3
from pathlib import Path

import httpx
import pytest

from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.key_encryption import APIKeyCipher
from course2career.llm_provider import ProviderName
from course2career.model_capability import (
    CapabilitySupport,
    LifecycleStatus,
    ModelStatus,
    Verification,
)
from course2career.model_discovery import CatalogError, ModelCatalogService
from course2career.permissions import PermissionDeniedError, Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_registry import (
    DiscoveryStrategy,
    get_provider_preset,
    ui_provider_presets,
)
from course2career.user_repository import StoredUser


@pytest.fixture
def setup(tmp_path: Path):
    repository = SQLiteProductRepository(tmp_path / "catalog.db")
    keys = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
    modes = BYOKModeService(repository)

    def add_user(user_id: str) -> Principal:
        repository.add(
            StoredUser(
                id=user_id,
                username=user_id,
                username_normalized=user_id,
                password_hash="unused-test-hash",
                role=Role.USER,
                plan=Plan.FREE,
                created_time="2026-09-24T00:00:00+00:00",
            )
        )
        principal = Principal(
            role=Role.USER, plan=Plan.FREE, user_id=user_id, session_version=1
        )
        modes.set_enabled(principal, True)
        return AuthService(repository).refresh_principal(principal)

    return repository, keys, modes, add_user


def test_mainland_order_and_discovery_strategies() -> None:
    presets = ui_provider_presets()
    assert [preset.provider_id for preset in presets] == [
        ProviderName.DEEPSEEK,
        ProviderName.BAILIAN,
        ProviderName.SILICONFLOW,
        ProviderName.MOONSHOT,
        ProviderName.ZHIPU,
        ProviderName.MINIMAX,
        ProviderName.OPENAI,
        ProviderName.ANTHROPIC,
        ProviderName.GEMINI,
        ProviderName.OPENROUTER,
    ]
    assert get_provider_preset(ProviderName.MOONSHOT).model_discovery_strategy == (
        DiscoveryStrategy.STATIC_OFFICIAL_CATALOG
    )
    assert get_provider_preset(ProviderName.ZHIPU).model_discovery_strategy == (
        DiscoveryStrategy.STATIC_OFFICIAL_CATALOG
    )
    assert get_provider_preset(ProviderName.MINIMAX).model_discovery_strategy == (
        DiscoveryStrategy.MINIMAX_MODELS
    )
    assert get_provider_preset(ProviderName.MINIMAX).allowed_endpoint_ids == (
        "cn",
        "global",
    )


def test_deepseek_mapping_alias_and_exact_model_verified(setup) -> None:
    _, keys, _, add_user = setup
    user = add_user("owner")
    keys.save_key(user, ProviderName.DEEPSEEK, "fake-deepseek-key")
    calls = []

    def getter(url, headers, params):
        calls.append((url, headers["Authorization"], params))
        return {
            "data": [
                {"id": "deepseek-flash", "owned_by": "deepseek"},
                {"id": "deepseek-v4-pro", "owned_by": "deepseek"},
                {"id": "deepseek-next", "owned_by": "deepseek"},
                {"id": "ignored", "owned_by": "other"},
                {"id": ["bad"], "owned_by": "deepseek"},
            ]
        }

    service = ModelCatalogService(keys, getter=getter)
    snapshot = service.discover_models(user, ProviderName.DEEPSEEK, "global")
    assert calls == [
        ("https://api.deepseek.com/models", "Bearer fake-deepseek-key", {})
    ]
    assert {item.model_id for item in snapshot.models} == {
        "deepseek-flash",
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek-next",
    }
    flash = next(item for item in snapshot.models if item.model_id == "deepseek-flash")
    alias = next(
        item for item in snapshot.models if item.model_id == "deepseek-v4-flash"
    )
    assert flash.context_window == 1_000_000
    assert flash.structured_output == CapabilitySupport.SUPPORTED
    assert flash.verification == Verification.VERIFIED
    assert flash.status == ModelStatus.VERIFIED
    assert flash.input_price == 1.0 and flash.output_price == 4.0
    assert flash.cached_input_price == 0.02 and flash.currency == "CNY"
    assert flash.pricing_source and flash.capability_source
    assert alias.lifecycle_status == LifecycleStatus.COMPATIBILITY_ALIAS
    assert alias.replacement_model == "deepseek-flash"
    assert alias.status == ModelStatus.COMPATIBILITY_ALIAS
    unknown = next(item for item in snapshot.models if item.model_id == "deepseek-next")
    assert unknown.status == ModelStatus.DISCOVERED
    assert unknown.input_price is None


def test_bailian_pagination_rich_metadata_and_region_isolation(setup) -> None:
    _, keys, _, add_user = setup
    user = add_user("owner")
    keys.save_key(user, ProviderName.BAILIAN, "fake-bailian-key")
    calls = []

    def getter(url, headers, params):
        calls.append((url, dict(params)))
        if params["page_no"] == "2":
            return {
                "output": {
                    "total": 2,
                    "models": [{"model": "qwen-other", "capabilities": ["TG"]}],
                }
            }
        return {
            "output": {
                "total": 2,
                "models": [
                    {
                        "model": "qwen-rich",
                        "name": "Qwen Rich",
                        "capabilities": ["TG", "Reasoning"],
                        "features": ["structured-outputs"],
                        "model_info": {
                            "context_window": 128000,
                            "max_output_tokens": 8192,
                        },
                        "prices": [
                            {
                                "range_name": "Default",
                                "prices": [
                                    {
                                        "type": "input_token",
                                        "price": "0.5",
                                        "price_unit": "per million tokens",
                                    },
                                    {
                                        "type": "output_token",
                                        "price": "2",
                                        "price_unit": "per million tokens",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        }

    service = ModelCatalogService(keys, getter=getter)
    bj = service.discover_models(
        user, ProviderName.BAILIAN, "cn-beijing", workspace_id="ws01"
    )
    rich = bj.models[0]
    assert len(bj.models) == 2
    assert rich.structured_output == CapabilitySupport.SUPPORTED
    assert rich.reasoning == CapabilitySupport.SUPPORTED
    assert rich.context_window == 128000 and rich.max_output_tokens == 8192
    assert rich.input_price == 0.5 and rich.output_price == 2.0
    assert rich.currency == "CNY" and rich.verification == Verification.UNKNOWN
    assert (
        service.peek(user, ProviderName.BAILIAN, "cn-beijing", workspace_id="ws02")
        is None
    )
    assert (
        service.peek(user, ProviderName.BAILIAN, "ap-southeast-1", workspace_id="ws01")
        is None
    )
    sg = service.discover_models(user, ProviderName.BAILIAN, "ap-southeast-1")
    assert sg.models[0].currency == "CNY"
    assert calls[0][0] == "https://ws01.cn-beijing.maas.aliyuncs.com/api/v1/models"
    assert calls[0][1]["capabilities"] == "TG"
    assert calls[-1][0] == "https://dashscope-intl.aliyuncs.com/api/v1/models"
    with pytest.raises(CatalogError, match="业务空间 ID"):
        service.discover_models(user, ProviderName.BAILIAN, "us-east-1")


def test_siliconflow_chat_and_unknown_price(setup) -> None:
    _, keys, _, add_user = setup
    user = add_user("owner")
    keys.save_key(user, ProviderName.SILICONFLOW, "fake-silicon-key")
    calls = []

    def getter(url, headers, params):
        calls.append((url, params))
        return {
            "data": [{"id": "org/chat-model", "object": "model", "owned_by": "org"}]
        }

    model = (
        ModelCatalogService(keys, getter=getter)
        .discover_models(user, ProviderName.SILICONFLOW, "cn")
        .models[0]
    )
    assert calls == [("https://api.siliconflow.cn/v1/models", {"sub_type": "chat"})]
    assert model.model_id == "org/chat-model"
    assert model.text_generation == CapabilitySupport.SUPPORTED
    assert model.input_price is None and model.currency is None
    assert model.pricing_source is None


def test_static_kimi_zhipu_and_minimax_selected_region(setup) -> None:
    _, keys, _, add_user = setup
    user = add_user("owner")
    calls = []

    def getter(url, headers, params):
        calls.append(url)
        return {"data": [{"id": "MiniMax-M3", "object": "model"}]}

    service = ModelCatalogService(keys, getter=getter)
    kimi = service.discover_models(user, ProviderName.MOONSHOT, "cn")
    assert {item.model_id for item in kimi.models} == {
        "kimi-k2.6",
        "kimi-k2.7-code",
        "kimi-k3",
    }
    assert kimi.models[0].currency == "CNY"
    glm = service.discover_models(user, ProviderName.ZHIPU, "cn").models[0]
    assert glm.model_id == "glm-5.1" and glm.input_price is None
    assert (
        glm.currency == "CNY" and glm.structured_output == CapabilitySupport.SUPPORTED
    )
    keys.save_key(user, ProviderName.MINIMAX, "fake-minimax-key")
    model = service.discover_models(user, ProviderName.MINIMAX, "cn").models[0]
    assert model.model_id == "MiniMax-M3" and model.context_window == 1_000_000
    service.discover_models(user, ProviderName.MINIMAX, "global")
    assert calls == [
        "https://api.minimaxi.com/v1/models",
        "https://api.minimax.io/v1/models",
    ]


def test_openrouter_usd_and_auto_excluded(setup) -> None:
    _, keys, _, add_user = setup
    user = add_user("owner")
    keys.save_key(user, ProviderName.OPENROUTER, "fake-openrouter-key")

    def getter(url, headers, params):
        return {
            "data": [
                {"id": "openrouter/auto"},
                {
                    "id": "vendor/model",
                    "name": "Model",
                    "context_length": 100000,
                    "architecture": {"output_modalities": ["text"]},
                    "supported_parameters": ["response_format"],
                    "pricing": {"prompt": "0.000001", "completion": "0.000004"},
                },
            ]
        }

    models = (
        ModelCatalogService(keys, getter=getter)
        .discover_models(user, ProviderName.OPENROUTER, "global")
        .models
    )
    assert len(models) == 1
    assert models[0].model_id == "vendor/model"
    assert models[0].input_price == 1 and models[0].output_price == 4
    assert models[0].currency == "USD" and models[0].pricing_source
    assert models[0].status == ModelStatus.CAPABILITY_ELIGIBLE


def test_cache_ttl_refresh_stale_key_scope_and_mode_toggle(setup) -> None:
    _, keys, modes, add_user = setup
    alice, bob = add_user("alice"), add_user("bob")
    keys.save_key(alice, ProviderName.DEEPSEEK, "fake-key-alice")
    keys.save_key(bob, ProviderName.DEEPSEEK, "fake-key-bob")
    tick = [0.0]
    calls = []

    def getter(url, headers, params):
        calls.append(headers["Authorization"])
        if len(calls) == 3:
            raise httpx.ConnectError("sensitive upstream text fake-key-alice")
        return {"data": [{"id": "deepseek-flash", "owned_by": "deepseek"}]}

    service = ModelCatalogService(
        keys, getter=getter, clock=lambda: tick[0], ttl_seconds=5
    )
    first = service.discover_models(alice, ProviderName.DEEPSEEK, "global")
    assert service.discover_models(alice, ProviderName.DEEPSEEK, "global") == first
    assert service.peek(bob, ProviderName.DEEPSEEK, "global") is None
    service.discover_models(bob, ProviderName.DEEPSEEK, "global")
    tick[0] = 6
    assert service.peek(alice, ProviderName.DEEPSEEK, "global").stale
    stale = service.discover_models(
        alice, ProviderName.DEEPSEEK, "global", force_refresh=True
    )
    assert stale.stale and stale.models == first.models
    assert "fake-key" not in stale.warning
    assert service.peek(alice, ProviderName.DEEPSEEK, "global").stale
    assert service.peek(alice, ProviderName.DEEPSEEK, "global").warning
    modes.set_enabled(alice, False)
    with pytest.raises(PermissionDeniedError):
        service.peek(alice, ProviderName.DEEPSEEK, "global")
    with pytest.raises(PermissionDeniedError):
        service.discover_models(alice, ProviderName.DEEPSEEK, "global")
    modes.set_enabled(alice, True)
    restored = AuthService(keys.repository).refresh_principal(alice)
    assert service.peek(restored, ProviderName.DEEPSEEK, "global") is not None
    keys.save_key(restored, ProviderName.DEEPSEEK, "fake-key-rotated")
    assert service.peek(restored, ProviderName.DEEPSEEK, "global") is None


def test_auth_failure_and_malformed_metadata_are_safe(setup) -> None:
    _, keys, _, add_user = setup
    user = add_user("owner")
    keys.save_key(user, ProviderName.OPENAI, "fake-openai-key")

    def unauthorized(url, headers, params):
        request = httpx.Request("GET", url)
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError(
            "secret upstream body", request=request, response=response
        )

    service = ModelCatalogService(keys, getter=unauthorized)
    with pytest.raises(CatalogError, match="鉴权失败") as error:
        service.discover_models(user, ProviderName.OPENAI, "global")
    assert "secret" not in str(error.value)
    assert (
        service.selected_model(
            user, ProviderName.OPENAI, "global", "gpt-any"
        ).verification
        == Verification.UNKNOWN
    )
    service = ModelCatalogService(
        keys, getter=lambda *_: {"data": [{"id": ["invalid"]}]}
    )
    with pytest.raises(CatalogError, match="没有可用于文本生成"):
        service.discover_models(user, ProviderName.OPENAI, "global")


def test_catalog_decryption_failure_is_sanitized(setup) -> None:
    repository, keys, _, add_user = setup
    user = add_user("owner")
    keys.save_key(user, ProviderName.OPENAI, "fake-openai-key")
    wrong_cipher = APIKeyService(repository, APIKeyCipher(bytes(range(1, 33))))
    service = ModelCatalogService(wrong_cipher, getter=lambda *_: {"data": []})
    with pytest.raises(CatalogError, match="无法解密"):
        service.discover_models(user, ProviderName.OPENAI, "global")


def test_existing_profile_table_gains_workspace_without_losing_selection(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy-profile.db"
    SQLiteProductRepository(path)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE user_provider_profiles")
        connection.execute(
            "CREATE TABLE user_provider_profiles ("
            "user_id TEXT NOT NULL, provider TEXT NOT NULL, "
            "endpoint_id TEXT NOT NULL, model_id TEXT NOT NULL, "
            "created_time TEXT NOT NULL, updated_time TEXT NOT NULL, "
            "PRIMARY KEY (user_id, provider))"
        )
        connection.execute(
            "INSERT INTO user_provider_profiles VALUES (?, ?, ?, ?, ?, ?)",
            ("old-user", "bailian", "cn-beijing", "qwen3.8-flash", "old", "old"),
        )
    upgraded = SQLiteProductRepository(path)
    profile = upgraded.get_provider_profile("old-user", "bailian")
    assert profile is not None
    assert profile.model_id == "qwen3.8-flash"
    assert profile.workspace_id is None
    SQLiteProductRepository(path)


def test_bailian_future_offline_date_is_deprecated_not_retired(setup) -> None:
    _, keys, _, add_user = setup
    user = add_user("owner")
    keys.save_key(user, ProviderName.BAILIAN, "fake-bailian-key")
    service = ModelCatalogService(
        keys,
        getter=lambda *_: {
            "output": {
                "total": 1,
                "models": [
                    {
                        "model": "qwen-future",
                        "inference_offline_info": {
                            "offline_time": "2099-01-01 00:00:00"
                        },
                        "prices": [
                            {
                                "range_name": "32k<Input<=128k",
                                "prices": [
                                    {
                                        "type": "input_token",
                                        "price": "3",
                                        "price_unit": "per million tokens",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        },
    )
    model = service.discover_models(
        user, ProviderName.BAILIAN, "cn-beijing", workspace_id="ws01"
    ).models[0]
    assert model.lifecycle_status == LifecycleStatus.DEPRECATED
    assert model.input_price is None
