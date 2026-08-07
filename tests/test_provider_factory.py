from pathlib import Path

import pytest

from course2career.api_key_service import APIKeyService
from course2career.config import Settings
from course2career.key_encryption import APIKeyCipher
from course2career.llm_client import OpenAIJDClient
from course2career.llm_provider import ProviderName
from course2career.llm_providers import DeepSeekProvider, ProviderError
from course2career.model_catalog import ModelSelection
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_factory import LLMProviderFactory
from course2career.user_repository import StoredUser


def test_factory_creates_provider_from_system_environment_keys() -> None:
    factory = LLMProviderFactory(
        Settings(
            openai_api_key="system-openai-key",
            deepseek_api_key="system-deepseek-key",
        )
    )

    openai_provider = factory.create(
        Principal(),
        provider=ProviderName.OPENAI,
        key_mode="system",
        model="test-openai-model",
    )
    deepseek_provider = factory.create(
        Principal(),
        provider=ProviderName.DEEPSEEK,
        key_mode="system",
        model="deepseek-v4-flash",
    )

    assert isinstance(openai_provider, OpenAIJDClient)
    assert openai_provider.model_name == "test-openai-model"
    assert isinstance(deepseek_provider, DeepSeekProvider)


def test_factory_uses_decrypted_developer_key(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "test.db")
    repository.add(
        StoredUser(
            id="developer-1",
            username="developer",
            username_normalized="developer",
            password_hash="not-used",
            role=Role.DEVELOPER,
            plan=Plan.DEVELOPER,
            created_time="2026-07-23T00:00:00+00:00",
        )
    )
    developer = Principal(
        role=Role.DEVELOPER,
        plan=Plan.DEVELOPER,
        user_id="developer-1",
        username="developer",
    )
    cipher = APIKeyCipher(bytes(range(32)))
    key_service = APIKeyService(repository, cipher)
    key_service.save_key(developer, ProviderName.DEEPSEEK, "developer-deepseek-key")
    factory = LLMProviderFactory(Settings(), key_service)

    provider = factory.create(
        developer,
        provider=ProviderName.DEEPSEEK,
        key_mode="user",
        model="deepseek-v4-pro",
    )

    assert isinstance(provider, DeepSeekProvider)
    assert provider.model_name == "deepseek-v4-pro"


def test_factory_rejects_missing_system_key() -> None:
    factory = LLMProviderFactory(Settings(openai_api_key=None))

    with pytest.raises(ProviderError, match="未配置平台 OpenAI API Key"):
        factory.create(
            Principal(),
            provider=ProviderName.OPENAI,
            key_mode="system",
            model="test-model",
        )


def test_factory_resolves_auto_safe_deepseek_model_and_fallbacks() -> None:
    class FakeCatalog:
        def resolve(self, *_args: object, **_kwargs: object) -> ModelSelection:
            return ModelSelection(
                primary_model="deepseek-v4-pro",
                fallback_models=("deepseek-v4-flash",),
                source="live_catalog",
            )

    factory = LLMProviderFactory(
        Settings(
            deepseek_api_key="system-key",
            deepseek_model_mode="auto_safe",
            deepseek_model_preference=("deepseek-v4-pro", "deepseek-v4-flash"),
            deepseek_max_output_tokens=900,
        ),
        model_catalog=FakeCatalog(),  # type: ignore[arg-type]
    )

    provider = factory.create(
        Principal(),
        provider=ProviderName.DEEPSEEK,
        key_mode="system",
        model="deepseek-v4-flash",
    )

    assert isinstance(provider, DeepSeekProvider)
    assert provider.model_name == "deepseek-v4-pro"
    assert provider.fallback_models == ("deepseek-v4-flash",)
    assert provider.max_output_tokens == 900


def test_factory_blocks_system_ai_when_global_switch_is_disabled() -> None:
    factory = LLMProviderFactory(
        Settings(
            deepseek_api_key="system-key",
            system_ai_enabled=False,
        )
    )

    with pytest.raises(ProviderError, match="系统AI当前已暂停"):
        factory.create(
            Principal(),
            provider=ProviderName.DEEPSEEK,
            key_mode="system",
            model="deepseek-v4-flash",
        )
