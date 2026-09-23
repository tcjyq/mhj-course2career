from types import SimpleNamespace

import pytest

from course2career.config import Settings
from course2career.llm_provider import LLMProvider, ProviderName
from course2career.llm_providers import OpenAICompatibleChatProvider, ProviderError
from course2career.models import JobAnalysis
from course2career.provider_registry import (
    PROVIDER_PRESETS,
    get_provider_preset,
    ui_provider_presets,
)


def test_registry_has_ten_stable_ids_and_labels() -> None:
    assert set(PROVIDER_PRESETS) == set(ProviderName)
    assert {item.provider_id.value for item in PROVIDER_PRESETS.values()} == {
        "deepseek",
        "openai",
        "bailian",
        "openrouter",
        "siliconflow",
        "moonshot",
        "zhipu",
        "minimax",
        "gemini",
        "anthropic",
    }
    assert get_provider_preset("bailian").display_name == "阿里云百炼"
    assert get_provider_preset("openrouter").display_name == "OpenRouter"
    assert [preset.provider_id for preset in ui_provider_presets()] == [
        ProviderName.OPENAI,
        ProviderName.DEEPSEEK,
        ProviderName.BAILIAN,
        ProviderName.OPENROUTER,
        ProviderName.SILICONFLOW,
        ProviderName.MOONSHOT,
        ProviderName.ZHIPU,
        ProviderName.MINIMAX,
        ProviderName.GEMINI,
        ProviderName.ANTHROPIC,
    ]


def test_registry_rejects_unknown_provider_and_unapproved_bailian_region() -> None:
    with pytest.raises(ValueError, match="不支持的模型供应商"):
        get_provider_preset("attacker")
    with pytest.raises(ValueError, match="不支持的百炼服务区域"):
        get_provider_preset(
            ProviderName.BAILIAN, Settings(bailian_region="http://localhost")
        )


def test_registry_selects_only_known_bailian_endpoints() -> None:
    assert get_provider_preset(ProviderName.BAILIAN).base_url == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert (
        get_provider_preset(
            ProviderName.BAILIAN, Settings(bailian_region="us-east-1")
        ).base_url
        == "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    )
    assert get_provider_preset(ProviderName.OPENROUTER).base_url == (
        "https://openrouter.ai/api/v1"
    )
    assert (
        get_provider_preset(
            ProviderName.BAILIAN,
            Settings(
                bailian_base_url="https://dashscope-us.aliyuncs.com/compatible-mode/v1"
            ),
        ).base_url
        == "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    )
    with pytest.raises(ValueError, match="受控区域端点"):
        get_provider_preset(
            ProviderName.BAILIAN,
            Settings(bailian_base_url="http://127.0.0.1/internal"),
        )


def test_registry_cost_metadata_uses_provider_specific_config() -> None:
    settings = Settings(
        deepseek_input_cost_per_million=1.0,
        deepseek_output_cost_per_million=2.0,
        bailian_input_cost_per_million=3.0,
        bailian_output_cost_per_million=4.0,
    )
    assert get_provider_preset(ProviderName.DEEPSEEK).cost_rates(settings) == (1.0, 2.0)
    assert get_provider_preset(ProviderName.BAILIAN).cost_rates(settings) == (3.0, 4.0)
    assert get_provider_preset(ProviderName.OPENROUTER).cost_rates(settings) == (
        0.0,
        0.0,
    )


def test_registry_uses_configured_legacy_models_and_explicit_openrouter_model() -> None:
    settings = Settings(
        openai_model="configured-openai", deepseek_model="deepseek-v4-pro"
    )
    assert get_provider_preset(ProviderName.OPENAI).configured_model(settings) == (
        "configured-openai"
    )
    assert get_provider_preset(ProviderName.DEEPSEEK).configured_model(settings) == (
        "deepseek-v4-pro"
    )
    assert get_provider_preset(ProviderName.BAILIAN).configured_model(settings) == (
        "qwen-plus"
    )
    assert (
        get_provider_preset(ProviderName.OPENROUTER).configured_model(settings) is None
    )


@pytest.mark.parametrize("provider", [ProviderName.BAILIAN, ProviderName.OPENROUTER])
def test_compatible_adapter_parses_mock_response_and_usage(
    provider: ProviderName,
) -> None:
    content = JobAnalysis(job_title="分析师", source="ai").model_dump_json()
    calls: list[dict[str, object]] = []

    def create(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=30, completion_tokens=12),
            model=kwargs["model"],
            system_fingerprint="fp-test",
        )

    sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    preset = get_provider_preset(provider)
    model = preset.default_model or "selected/model"
    adapter = OpenAICompatibleChatProvider(
        preset=preset, api_key="fake-key", model=model, sdk_client=sdk
    )

    assert isinstance(adapter, LLMProvider)
    assert adapter.extract_job_skills("测试JD").job_title == "分析师"
    assert adapter.provider_name == provider
    assert adapter.last_usage is not None
    assert adapter.last_usage.model == model
    assert adapter.last_usage.input_tokens == 30
    assert adapter.last_usage.output_tokens == 12
    assert adapter.last_usage.system_fingerprint == "fp-test"
    assert calls[0]["model"] == model
    assert "response_format" not in calls[0]
    assert "extra_body" not in calls[0]


def test_openrouter_requires_explicit_model_in_foundation() -> None:
    with pytest.raises(ProviderError, match="配置无效"):
        OpenAICompatibleChatProvider(
            preset=get_provider_preset(ProviderName.OPENROUTER),
            api_key="fake-key",
            model="",
            sdk_client=object(),
        )
