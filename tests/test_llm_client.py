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
            self.with_raw_response = self

        def parse(self, **kwargs: object) -> SimpleNamespace:
            self.kwargs = kwargs
            return SimpleNamespace(
                http_response=SimpleNamespace(
                    json=lambda: {
                        "usage": {"input_tokens": 321, "output_tokens": 123},
                    }
                ),
                parse=lambda: SimpleNamespace(output_parsed=parsed),
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
        @property
        def with_raw_response(self):
            return self

        def parse(self, **kwargs: object) -> None:
            raise RuntimeError("provider detail")

    sdk = SimpleNamespace(responses=BrokenResponses())
    client = OpenAIJDClient(Settings(openai_api_key="test-key"), sdk_client=sdk)

    with pytest.raises(LLMClientError, match="大模型服务暂时不可用"):
        client.extract_job_skills("数据分析师岗位，要求熟练使用 SQL 完成数据查询。")


@pytest.mark.parametrize(
    "returned_model", ["requested-model", "unfamiliar-server-model", None]
)
def test_real_sdk_schema_failure_keeps_raw_identity_and_usage(returned_model):
    import httpx
    from openai import OpenAI

    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "resp_synthetic",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": returned_model,
                "output": [
                    {
                        "id": "msg_synthetic",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "annotations": [],
                                "text": '{"skills": "invalid"}',
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 10,
                    "total_tokens": 30,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0},
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
        sdk = OpenAI(api_key="synthetic-only", max_retries=0, http_client=http_client)
        client = OpenAIJDClient(
            Settings(openai_api_key="synthetic-only", openai_model="requested-model"),
            sdk_client=sdk,
        )
        with pytest.raises(LLMClientError):
            client.extract_job_skills("synthetic SQL")
        assert len(requests) == 1
        assert client.last_trace.attempts[0].response_received
        assert client.last_trace.returned_model == returned_model
        assert client.last_trace.attempts[0].error_code == "SCHEMA_VALIDATION_FAILED"
        assert client.last_usage.input_tokens == 20
        assert client.last_usage.output_tokens == 10
        assert client.last_result is None


def test_openai_endpoint_cannot_be_overridden_by_ambient_sdk_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.example.invalid/v1")
    client = OpenAIJDClient(Settings(openai_api_key="synthetic-only"))
    try:
        assert str(client.client.base_url) == "https://api.openai.com/v1/"
        assert client.client.max_retries == 0
        assert client.endpoint == "https://api.openai.com/v1"
    finally:
        client.client.close()
