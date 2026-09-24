import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from course2career.access_services import AIUsageService
from course2career.api_key_service import APIKeyService
from course2career.config import Settings
from course2career.key_encryption import APIKeyCipher, KeyDecryptionError
from course2career.llm_client import OpenAIJDClient
from course2career.llm_provider import LLMProvider, ProviderName
from course2career.llm_providers import (
    DeepSeekProvider,
    OpenAICompatibleChatProvider,
    ProviderError,
)
from course2career.model_capability import (
    CapabilitySupport,
    Verification,
    model_capability,
)
from course2career.model_catalog import _create_deepseek_client
from course2career.models import JobAnalysis
from course2career.native_providers import AnthropicMessagesProvider, GeminiProvider
from course2career.permissions import PermissionDeniedError, Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_connection import (
    test_provider_connection as check_connection,
)
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_profile import ProviderProfileService
from course2career.provider_registry import (
    PROVIDER_PRESETS,
    ProviderProtocol,
    get_provider_preset,
)
from course2career.ui.analysis_page import configured_byok_providers
from course2career.user_repository import StoredUser


def _principal(repository: SQLiteProductRepository, user_id: str) -> Principal:
    repository.add(
        StoredUser(
            id=user_id,
            username=user_id,
            username_normalized=user_id,
            password_hash="not-used",
            role=Role.DEVELOPER,
            plan=Plan.DEVELOPER,
            created_time="2026-09-23T00:00:00+00:00",
        )
    )
    return Principal(role=Role.DEVELOPER, plan=Plan.DEVELOPER, user_id=user_id)


def test_ten_presets_map_to_four_protocols_and_fixed_endpoints() -> None:
    assert len(PROVIDER_PRESETS) == 10
    assert {preset.primary_protocol for preset in PROVIDER_PRESETS.values()} == set(
        ProviderProtocol
    )
    chat_ids = {
        ProviderName.BAILIAN,
        ProviderName.OPENROUTER,
        ProviderName.SILICONFLOW,
        ProviderName.MOONSHOT,
        ProviderName.ZHIPU,
        ProviderName.MINIMAX,
    }
    assert all(
        get_provider_preset(item).primary_protocol == ProviderProtocol.OPENAI_CHAT
        for item in chat_ids
    )
    for preset in PROVIDER_PRESETS.values():
        assert preset.base_url.startswith("https://")
        assert preset.selected_endpoint_id in preset.allowed_endpoint_ids
        assert preset.api_key_help_url.startswith("https://")
        assert "api_key" not in preset.__dict__
        with pytest.raises(ValueError, match="官方端点"):
            preset.endpoint("http://127.0.0.1/private")
    assert get_provider_preset(ProviderName.DEEPSEEK).supports_model_discovery
    assert get_provider_preset(ProviderName.GEMINI).supports_model_discovery


def test_profile_is_user_scoped_and_contains_no_secret(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "profiles.db")
    alice = _principal(repository, "alice")
    bob = _principal(repository, "bob")
    profiles = ProviderProfileService(repository)
    saved = profiles.save(alice, ProviderName.MOONSHOT, "cn", "kimi-k2.5")
    assert profiles.get(alice, ProviderName.MOONSHOT) == saved
    assert profiles.get(bob, ProviderName.MOONSHOT) is None
    assert (
        saved.created_time
        == profiles.save(alice, ProviderName.MOONSHOT, "cn", "kimi-k2.5").created_time
    )
    assert "key" not in saved.__dict__
    with pytest.raises(ValueError, match="官方端点"):
        profiles.save(alice, ProviderName.MOONSHOT, "custom", "kimi-k2.5")
    with pytest.raises(ValueError, match="模型 ID"):
        profiles.save(alice, ProviderName.MOONSHOT, "cn", "bad\nmodel")
    with pytest.raises(PermissionDeniedError):
        profiles.save(
            Principal(role=Role.USER, plan=Plan.PRO, user_id="bob"),
            ProviderName.MOONSHOT,
            "cn",
            "kimi-k2.5",
        )


def test_new_key_validation_failure_preserves_existing_ciphertext(
    tmp_path: Path,
) -> None:
    repository = SQLiteProductRepository(tmp_path / "keys.db")
    alice = _principal(repository, "alice")
    service = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
    service.save_key(alice, ProviderName.GEMINI, "old-fake-key")
    before = repository.get_api_key("alice", "gemini")

    def reject(_key: str) -> None:
        raise ValueError("validation failed")

    with pytest.raises(ValueError, match="validation failed"):
        service.save_key(alice, ProviderName.GEMINI, "new-fake-key", validator=reject)
    assert repository.get_api_key("alice", "gemini") == before
    assert service.get_key(alice, ProviderName.GEMINI) == "old-fake-key"
    service.save_key(alice, ProviderName.GEMINI, "new-fake-key")
    assert service.get_key(alice, ProviderName.GEMINI) == "new-fake-key"
    with pytest.raises(KeyDecryptionError):
        service.cipher.decrypt(
            service.cipher.encrypt(
                "fake", user_id="alice", provider=ProviderName.GEMINI
            ),
            user_id="alice",
            provider=ProviderName.ANTHROPIC,
        )
    service.delete_key(alice, ProviderName.GEMINI)
    assert service.list_keys(alice) == []


@pytest.mark.parametrize(
    "legacy_ids",
    [
        ("openai", "deepseek"),
        ("openai", "deepseek", "bailian", "openrouter"),
    ],
)
def test_key_schema_migration_preserves_rows_and_repeated_startup(
    tmp_path: Path, legacy_ids: tuple[str, ...]
) -> None:
    path = tmp_path / "legacy.db"
    repository = SQLiteProductRepository(path)
    alice = _principal(repository, "alice")
    cipher = APIKeyCipher(bytes(range(32)))
    encrypted = cipher.encrypt(
        "legacy-fake-key", user_id="alice", provider=ProviderName.OPENAI
    )
    ddl_ids = ", ".join(f"'{item}'" for item in legacy_ids)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE user_api_keys")
        connection.execute(
            "CREATE TABLE user_api_keys ("
            "user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
            f"provider TEXT NOT NULL CHECK (provider IN ({ddl_ids})), "
            "encrypted_key BLOB NOT NULL, nonce BLOB NOT NULL, "
            "last_four TEXT NOT NULL, updated_time TEXT NOT NULL, "
            "PRIMARY KEY (user_id, provider))"
        )
        connection.execute(
            "INSERT INTO user_api_keys VALUES (?, ?, ?, ?, ?, ?)",
            (
                "alice",
                "openai",
                encrypted.ciphertext,
                encrypted.nonce,
                "-key",
                "2026-07-01T00:00:00+00:00",
            ),
        )
    for _ in range(2):
        upgraded = SQLiteProductRepository(path)
        row = upgraded.get_api_key("alice", "openai")
        assert row is not None
        assert (row.encrypted_key, row.nonce, row.updated_time) == (
            encrypted.ciphertext,
            encrypted.nonce,
            "2026-07-01T00:00:00+00:00",
        )
        assert (
            APIKeyService(upgraded, cipher).get_key(alice, ProviderName.OPENAI)
            == "legacy-fake-key"
        )
    APIKeyService(upgraded, cipher).save_key(
        alice, ProviderName.ANTHROPIC, "new-fake-key"
    )


def test_failed_key_schema_migration_rolls_back_old_table(tmp_path: Path) -> None:
    path = tmp_path / "rollback.db"
    repository = SQLiteProductRepository(path)
    _principal(repository, "alice")
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE user_api_keys")
        connection.execute(
            "CREATE TABLE user_api_keys ("
            "user_id TEXT NOT NULL, "
            "provider TEXT NOT NULL CHECK (provider IN ('openai', 'deepseek')), "
            "encrypted_key BLOB NOT NULL, nonce BLOB NOT NULL, "
            "last_four TEXT NOT NULL, updated_time TEXT NOT NULL, "
            "PRIMARY KEY (user_id, provider))"
        )
        connection.execute(
            "INSERT INTO user_api_keys VALUES (?, ?, ?, ?, ?, ?)",
            ("alice", "openai", b"ciphertext", b"bad", "-key", "unchanged"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        SQLiteProductRepository(path)
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT nonce, updated_time FROM user_api_keys"
        ).fetchone()
        temp_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'user_api_keys_c08'"
        ).fetchone()
    assert row == (b"bad", "unchanged")
    assert temp_table is None


@pytest.mark.parametrize(
    "provider",
    [
        ProviderName.BAILIAN,
        ProviderName.OPENROUTER,
        ProviderName.SILICONFLOW,
        ProviderName.MOONSHOT,
        ProviderName.ZHIPU,
        ProviderName.MINIMAX,
    ],
)
def test_shared_chat_adapter_uses_official_endpoint_and_validates_json(
    provider: ProviderName,
) -> None:
    captured: list[dict[str, object]] = []
    content = JobAnalysis(job_title="分析师", source="ai").model_dump_json()

    def create(**kwargs: object) -> SimpleNamespace:
        captured.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3),
            model=kwargs["model"],
        )

    sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    preset = get_provider_preset(provider)
    adapter = OpenAICompatibleChatProvider(
        preset=preset, api_key="fake-api-key", model="test/model", sdk_client=sdk
    )
    assert isinstance(adapter, LLMProvider)
    assert adapter.extract_job_skills("合成 JD").job_title == "分析师"
    assert adapter.last_usage is not None
    assert adapter.last_usage.input_tokens == 7
    assert adapter.last_usage.output_tokens == 3
    assert captured[0]["model"] == "test/model"
    assert "response_format" not in captured[0]
    assert ("extra_body" in captured[0]) == (provider == ProviderName.MINIMAX)


def test_sdk_clients_do_not_follow_cross_origin_redirects() -> None:
    clients = [
        OpenAIJDClient(Settings(openai_api_key="fake-secret")).client,
        DeepSeekProvider(api_key="fake-secret", model="deepseek-v4-flash").client,
        OpenAICompatibleChatProvider(
            preset=get_provider_preset(ProviderName.MOONSHOT),
            api_key="fake-secret",
            model="fake-model",
        ).client,
        _create_deepseek_client("fake-secret", 30),
    ]
    try:
        assert all(not client._client.follow_redirects for client in clients)
    finally:
        for client in clients:
            client.close()


def test_native_messages_and_gemini_map_usage_and_sanitize_errors() -> None:
    content = JobAnalysis(job_title="分析师", source="ai").model_dump_json()
    observed: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def anthropic_transport(
        url: str, headers: dict[str, str], body: dict[str, object], _timeout: float
    ) -> dict[str, object]:
        observed.append((url, headers, body))
        return {
            "model": "claude-test-returned",
            "content": [{"type": "text", "text": content}],
            "usage": {"input_tokens": 11, "output_tokens": 5},
        }

    anthropic = AnthropicMessagesProvider(
        preset=get_provider_preset(ProviderName.ANTHROPIC),
        api_key="fake-secret",
        model="claude-test",
        transport=anthropic_transport,
    )
    assert isinstance(anthropic, LLMProvider)
    assert anthropic.extract_job_skills("合成 JD").job_title == "分析师"
    assert observed[0][0] == "https://api.anthropic.com/v1/messages"
    assert observed[0][1]["x-api-key"] == "fake-secret"
    assert observed[0][2]["messages"] == [{"role": "user", "content": "合成 JD"}]
    assert observed[0][2]["output_config"]["format"]["type"] == "json_schema"
    assert anthropic.last_usage is not None
    assert anthropic.last_usage.model == "claude-test-returned"

    def gemini_transport(
        url: str, headers: dict[str, str], body: dict[str, object], _timeout: float
    ) -> dict[str, object]:
        observed.append((url, headers, body))
        return {
            "modelVersion": "gemini-test-returned",
            "candidates": [{"content": {"parts": [{"text": content}]}}],
            "usageMetadata": {"promptTokenCount": 13, "candidatesTokenCount": 4},
        }

    gemini = GeminiProvider(
        preset=get_provider_preset(ProviderName.GEMINI),
        api_key="fake-secret",
        model="gemini-test",
        transport=gemini_transport,
    )
    assert isinstance(gemini, LLMProvider)
    assert gemini.extract_job_skills("合成 JD").job_title == "分析师"
    assert observed[1][0].endswith("/models/gemini-test:generateContent")
    assert observed[1][1] == {"x-goog-api-key": "fake-secret"}
    assert "responseJsonSchema" in observed[1][2]["generationConfig"]
    assert gemini.last_usage is not None
    assert gemini.last_usage.output_tokens == 4
    assert gemini.last_usage.model == "gemini-test-returned"

    gemini.transport = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("fake-secret should not appear")
    )
    with pytest.raises(ProviderError) as exc:
        gemini.extract_job_skills("合成 JD")
    assert "fake-secret" not in str(exc.value)
    assert gemini.last_usage is None
    with pytest.raises(ProviderError, match="配置无效"):
        GeminiProvider(
            preset=get_provider_preset(ProviderName.GEMINI),
            api_key="fake-secret",
            model="../internal",
            transport=gemini_transport,
        )


def test_model_capability_does_not_infer_all_models_from_provider() -> None:
    known = model_capability(ProviderName.DEEPSEEK, "deepseek-v4-flash")
    assert known.verification == Verification.UNKNOWN
    assert known.structured_output == CapabilitySupport.UNKNOWN
    assert (
        model_capability(ProviderName.DEEPSEEK, "unapproved-model").verification
        == Verification.UNKNOWN
    )
    assert (
        model_capability(ProviderName.GEMINI, "gemini-test").verification
        == Verification.UNKNOWN
    )


def test_connection_contract_runs_extraction_and_never_returns_secret() -> None:
    provider = SimpleNamespace(
        model_name="model-returned",
        last_usage=None,
        extract_job_skills=lambda _jd: JobAnalysis(job_title="合成岗位", source="ai"),
    )
    factory = SimpleNamespace(create=lambda *_args, **_kwargs: provider)
    principal = Principal(role=Role.DEVELOPER, plan=Plan.DEVELOPER, user_id="developer")
    result = check_connection(
        factory, principal, ProviderName.MOONSHOT, "model-requested"
    )
    assert result.schema_ok and result.request_ok and result.auth_ok
    assert result.model == "model-returned"
    assert result.sanitized_error is None

    failing = SimpleNamespace(
        create=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("fake-secret")
        )
    )
    failed = check_connection(
        failing, principal, ProviderName.MOONSHOT, "model-requested"
    )
    assert not failed.schema_ok
    assert "fake-secret" not in str(failed)
    with pytest.raises(PermissionDeniedError):
        check_connection(
            factory,
            Principal(role=Role.USER, plan=Plan.FREE, user_id="user"),
            ProviderName.MOONSHOT,
            "model-requested",
        )


def test_factory_routes_native_protocols_without_network(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "native.db")
    developer = _principal(repository, "developer")
    keys = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
    factory = LLMProviderFactory(Settings(), keys)
    for provider, model, adapter_type in (
        (ProviderName.ANTHROPIC, "claude-test", AnthropicMessagesProvider),
        (ProviderName.GEMINI, "gemini-test", GeminiProvider),
    ):
        keys.save_key(developer, provider, "fake-secret-key")
        adapter = factory.create(
            developer, provider=provider, key_mode="user", model=model
        )
        assert isinstance(adapter, adapter_type)
        assert adapter.model_name == model
        with pytest.raises(ProviderError, match="官方端点"):
            factory.create(
                developer,
                provider=provider,
                key_mode="user",
                model=model,
                endpoint_id="custom",
            )


def test_byok_filters_unconfigured_and_rejects_free_user(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "filter.db")
    developer = _principal(repository, "developer")
    keys = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
    profiles = ProviderProfileService(repository)
    assert configured_byok_providers(developer, keys, profiles) == ()
    keys.save_key(developer, ProviderName.GEMINI, "fake-gemini-key")
    assert configured_byok_providers(developer, keys, profiles) == ()
    profiles.save(developer, ProviderName.GEMINI, "global", "gemini-test")
    assert configured_byok_providers(developer, keys, profiles) == (
        ProviderName.GEMINI,
    )
    free_user = Principal(role=Role.USER, plan=Plan.FREE, user_id="free")
    assert configured_byok_providers(free_user, keys, profiles) == ()
    with pytest.raises(PermissionDeniedError):
        keys.save_key(free_user, ProviderName.GEMINI, "fake-free-key")
    with pytest.raises(PermissionDeniedError):
        keys.get_key(free_user, ProviderName.GEMINI)
    with pytest.raises(PermissionDeniedError):
        profiles.save(free_user, ProviderName.GEMINI, "global", "gemini-test")


def test_unknown_cost_and_byok_quota_separation(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "usage.db")
    developer = _principal(repository, "developer")
    usage = AIUsageService(repository)
    call_id = usage.start_call(developer, "user", "gemini-test", provider="gemini")
    usage.complete_call(usage_id=call_id, success=True)
    assert usage.get_quota_status(developer, "system").used == 0
    assert usage.get_quota_status(developer, "user").used == 1
    with sqlite3.connect(repository.database_path) as connection:
        row = connection.execute(
            "SELECT cost, cost_status FROM api_usage WHERE id = ?", (call_id,)
        ).fetchone()
    assert row == (0, "unknown")


@pytest.mark.parametrize(
    "role,plan,allowed",
    [
        (Role.GUEST, Plan.FREE, False),
        (Role.USER, Plan.FREE, False),
        (Role.DEVELOPER, Plan.DEVELOPER, True),
        (Role.ADMIN, Plan.ADMIN, True),
    ],
)
def test_registry_generated_card_visibility_by_role(
    tmp_path: Path, role: Role, plan: Plan, allowed: bool
) -> None:
    database_path = (tmp_path / f"{role.value}.db").as_posix()
    app = AppTest.from_string(
        f'''
from course2career.api_key_service import APIKeyService
from course2career.key_encryption import APIKeyCipher
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.ui.developer_page import render_developer_page
repository = SQLiteProductRepository(r"{database_path}")
principal = Principal(
    role=Role("{role.value}"), plan=Plan("{plan.value}"), user_id="test"
)
keys = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
render_developer_page(principal, keys, None)
'''
    ).run()
    assert not app.exception
    assert len([box for box in app.selectbox if box.label == "官方端点"]) == (
        10 if allowed else 0
    )
    if allowed:
        assert any("未验证" in str(item.value) for item in app.caption)


def test_developer_card_add_update_delete_and_reload(tmp_path: Path) -> None:
    database_path = (tmp_path / "card.db").as_posix()
    source = f'''
from course2career.api_key_service import APIKeyService
from course2career.key_encryption import APIKeyCipher
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.ui.developer_page import render_developer_page
from course2career.user_repository import StoredUser
repository = SQLiteProductRepository(r"{database_path}")
if repository.find_by_id("developer") is None:
    repository.add(StoredUser(
        "developer", "developer", "developer", "unused",
        Role.DEVELOPER, Plan.DEVELOPER, "2026-09-23T00:00:00+00:00"
    ))
principal = Principal(role=Role.DEVELOPER, plan=Plan.DEVELOPER, user_id="developer")
keys = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
render_developer_page(principal, keys, None)
'''
    app = AppTest.from_string(source).run()
    models = [field for field in app.text_input if field.label == "模型 ID"]
    secrets = [
        field
        for field in app.text_input
        if field.label == "API Key（更新时填写新 Key）"
    ]
    saves = [button for button in app.button if button.label == "保存配置"]
    models[8].set_value("gemini-test")
    secrets[8].set_value("fake-key-original")
    saves[8].click().run()
    assert not app.exception
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT model_id FROM user_provider_profiles WHERE provider = 'gemini'"
        ).fetchone()
    assert row == ("gemini-test",)
    assert (
        next(
            field
            for field in app.text_input
            if field.key.startswith("provider_secret_gemini")
        ).value
        == ""
    )

    app = AppTest.from_string(source).run()
    assert not app.exception
    assert any("fake-key-original" not in str(item.value) for item in app.markdown)
    model = next(
        field
        for field in app.text_input
        if field.key.startswith("provider_model_gemini")
    )
    model.set_value("gemini-next")
    [button for button in app.button if button.label == "保存配置"][8].click().run()
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT model_id FROM user_provider_profiles WHERE provider = 'gemini'"
        ).fetchone()
    assert row == ("gemini-next",)

    next(
        button for button in app.button if button.key == "delete_provider_gemini"
    ).click().run()
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM user_provider_profiles WHERE provider = 'gemini'"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM user_api_keys WHERE provider = 'gemini'"
            ).fetchone()[0]
            == 0
        )
