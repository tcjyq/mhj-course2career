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


def test_deepseek_provider_falls_back_once_when_model_is_missing() -> None:
    content = JobAnalysis(job_title="AI应用开发实习生", source="ai").model_dump_json()

    class MissingModelError(RuntimeError):
        status_code = 404

    class FakeCompletions:
        def __init__(self) -> None:
            self.models: list[str] = []

        def create(self, **kwargs: object) -> SimpleNamespace:
            model = str(kwargs["model"])
            self.models.append(model)
            if len(self.models) == 1:
                raise MissingModelError("model not found")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=100, completion_tokens=40),
                model=model,
                system_fingerprint="fp-test",
            )

    completions = FakeCompletions()
    provider = DeepSeekProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        fallback_models=("deepseek-v4-pro",),
        sdk_client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )

    provider.extract_job_skills("测试岗位")

    assert completions.models == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert provider.model_name == "deepseek-v4-pro"
    assert provider.last_usage is not None
    assert provider.last_usage.model == "deepseek-v4-pro"
    assert provider.last_usage.system_fingerprint == "fp-test"


def test_deepseek_provider_does_not_fallback_on_non_model_errors() -> None:
    class RateLimitError(RuntimeError):
        status_code = 429

    class FakeCompletions:
        def __init__(self) -> None:
            self.call_count = 0

        def create(self, **_kwargs: object) -> SimpleNamespace:
            self.call_count += 1
            raise RateLimitError("rate limited")

    completions = FakeCompletions()
    provider = DeepSeekProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        fallback_models=("deepseek-v4-pro",),
        sdk_client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )

    with pytest.raises(ProviderError, match="DeepSeek服务暂时不可用"):
        provider.extract_job_skills("测试岗位")

    assert completions.call_count == 1
    assert provider.model_name == "deepseek-v4-flash"
