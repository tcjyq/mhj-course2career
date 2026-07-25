from types import SimpleNamespace

import pytest

from course2career.config import Settings
from course2career.llm_client import LLMClientError, OpenAIJDClient
from course2career.models import JobAnalysis, JobSkill, SkillImportance


def test_openai_client_requests_structured_job_analysis() -> None:
    parsed = JobAnalysis(
        job_title="数据分析师",
        source="ai",
        skills=[
            JobSkill(
                name="SQL",
                normalized_name="SQL",
                category="数据能力",
                importance=SkillImportance.CORE,
                evidence_text="熟练使用 SQL",
            )
        ],
    )

    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def parse(self, **kwargs: object) -> SimpleNamespace:
            self.kwargs = kwargs
            return SimpleNamespace(
                output_parsed=parsed,
                usage=SimpleNamespace(input_tokens=321, output_tokens=123),
            )

    responses = FakeResponses()
    sdk = SimpleNamespace(responses=responses)
    client = OpenAIJDClient(
        Settings(openai_api_key="test-key", openai_model="test-model"), sdk_client=sdk
    )

    result = client.extract_job_skills(
        "数据分析师岗位，要求熟练使用 SQL 完成数据查询。"
    )

    assert result == parsed
    assert responses.kwargs["model"] == "test-model"
    assert responses.kwargs["text_format"] is JobAnalysis
    assert responses.kwargs["max_output_tokens"] == 1500
    assert client.last_usage is not None
    assert client.last_usage.input_tokens == 321
    assert client.last_usage.output_tokens == 123


def test_openai_client_wraps_provider_errors() -> None:
    class BrokenResponses:
        def parse(self, **kwargs: object) -> None:
            raise RuntimeError("provider detail")

    sdk = SimpleNamespace(responses=BrokenResponses())
    client = OpenAIJDClient(Settings(openai_api_key="test-key"), sdk_client=sdk)

    with pytest.raises(LLMClientError, match="大模型服务暂时不可用"):
        client.extract_job_skills("数据分析师岗位，要求熟练使用 SQL 完成数据查询。")
