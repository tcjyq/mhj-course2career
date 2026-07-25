from types import SimpleNamespace

import pytest

from course2career.llm_provider import LLMProvider, ProviderName
from course2career.llm_providers import DeepSeekProvider, ProviderError
from course2career.models import JobAnalysis


def test_deepseek_provider_uses_json_mode_and_validates_domain_model() -> None:
    content = JobAnalysis(
        job_title="数据分析师",
        source="ai",
        skills=[],
    ).model_dump_json()

    class FakeCompletions:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def create(self, **kwargs: object) -> SimpleNamespace:
            self.kwargs = kwargs
            message = SimpleNamespace(content=content)
            usage = SimpleNamespace(prompt_tokens=210, completion_tokens=90)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)],
                usage=usage,
            )

    completions = FakeCompletions()
    sdk = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = DeepSeekProvider(
        api_key="test-deepseek-key",
        model="deepseek-v4-flash",
        sdk_client=sdk,
    )

    result = provider.extract_job_skills(
        "数据分析师岗位，负责使用SQL完成数据查询和分析。"
    )

    assert isinstance(provider, LLMProvider)
    assert provider.provider_name == ProviderName.DEEPSEEK
    assert result.job_title == "数据分析师"
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["model"] == "deepseek-v4-flash"
    assert provider.last_usage is not None
    assert provider.last_usage.input_tokens == 210
    assert provider.last_usage.output_tokens == 90


def test_deepseek_provider_rejects_unapproved_model() -> None:
    with pytest.raises(ProviderError, match="不支持的 DeepSeek 模型"):
        DeepSeekProvider(api_key="test-key", model="unknown-model")
