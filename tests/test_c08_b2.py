"""B2 的本地确定性测试，不调用外部 API。"""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from course2career.llm_provider import LLMUsage, ProviderName
from course2career.model_capability import model_capability
from course2career.models import JobAnalysis, JobSkill
from course2career.provider_connection import (
    test_provider_connection as check_connection,
)
from course2career.provider_error_classification import classify_provider_error
from course2career.provider_registry import get_provider_preset
from course2career.provider_validation import (
    ValidationFixture,
    fixture_passes,
    load_fixtures,
    validate_provider,
)
from course2career.provider_verification import (
    ProviderErrorCode,
    Verification,
    VerificationRecord,
    get_record,
    now_utc,
    save_record,
)
from course2career.structured_output import (
    AnthropicSchemaAdapter,
    BailianSchemaAdapter,
    GeminiSchemaAdapter,
    StructuredOutputStrategy,
)


class FakeClient:
    model_name = "gpt-5.6-luna"

    def __init__(self, *, usage: bool = True, fail_at: int | None = None) -> None:
        self.usage = usage
        self.fail_at = fail_at
        self.calls = 0
        self.last_usage: LLMUsage | None = None

    def extract_job_skills(self, jd: str) -> JobAnalysis:
        self.calls += 1
        if self.calls == self.fail_at:
            raise TimeoutError("private-secret")
        self.last_usage = (
            LLMUsage(input_tokens=20, output_tokens=10, model=self.model_name)
            if self.usage
            else None
        )
        terms = [term for term in ("Python", "SQL", "需求分析", "Excel") if term in jd]
        return JobAnalysis(
            job_title="合成岗位",
            skills=[
                JobSkill(
                    name=term,
                    normalized_name=term,
                    category="技术",
                    evidence_text=term,
                )
                for term in terms
            ],
            source="ai",
        )


def test_strategy_map_and_schema_adapters_keep_original_contract() -> None:
    assert (
        get_provider_preset(ProviderName.DEEPSEEK).strategy_for_model(
            "deepseek-v4-flash"
        )
        == StructuredOutputStrategy.JSON_OBJECT
    )
    bailian = get_provider_preset(ProviderName.BAILIAN)
    assert bailian.strategy_for_model("qwen3.8-flash") == (
        StructuredOutputStrategy.STRICT_JSON_SCHEMA
    )
    assert (
        bailian.strategy_for_model("qwen-plus") == StructuredOutputStrategy.PROMPT_JSON
    )
    assert (
        get_provider_preset(ProviderName.ANTHROPIC).strategy_for_model(
            "claude-haiku-4-5-20251001"
        )
        == StructuredOutputStrategy.NATIVE_SCHEMA
    )
    assert "minLength" not in str(AnthropicSchemaAdapter.job_analysis_schema())
    assert "minLength" not in str(GeminiSchemaAdapter.job_analysis_schema())
    assert "default" not in str(GeminiSchemaAdapter.job_analysis_schema())
    strict = BailianSchemaAdapter.job_analysis_schema()
    assert strict["required"] == list(strict["properties"])
    assert strict["additionalProperties"] is False
    assert "minLength" in str(JobAnalysis.model_json_schema())


def test_fixture_suite_is_synthetic_and_checks_evidence() -> None:
    fixtures = load_fixtures()
    assert 3 <= len(fixtures) <= 5
    assert all(item.jd.startswith("合成岗位：") for item in fixtures)
    sample = ValidationFixture("x", "要求 SQL。", ("SQL",), ())
    valid = JobAnalysis(
        skills=[
            JobSkill(
                name="SQL", normalized_name="SQL", category="技术", evidence_text="SQL"
            )
        ]
    )
    assert fixture_passes(sample, valid)
    invalid = valid.model_copy(
        update={
            "skills": [valid.skills[0].model_copy(update={"evidence_text": "凭空"})]
        }
    )
    assert not fixture_passes(sample, invalid)


def test_verification_record_scopes_endpoint_and_model(tmp_path: Path) -> None:
    path = tmp_path / "records.json"
    preset = get_provider_preset(ProviderName.OPENAI)
    record = VerificationRecord(
        provider=ProviderName.OPENAI,
        endpoint_id="global",
        model="gpt-5.6-luna",
        protocol=preset.primary_protocol,
        schema_strategy=StructuredOutputStrategy.STRICT_JSON_SCHEMA,
        verified_at=now_utc(),
        fixture_count=4,
        fixture_passed=4,
        latency_ms=100,
        input_tokens=100,
        output_tokens=50,
        usage_available=True,
        cost_available=False,
        result=Verification.VERIFIED,
        external_calls=5,
        returned_model="gpt-5.6-luna",
    )
    save_record(record, path)
    assert get_record(ProviderName.OPENAI, "global", "gpt-5.6-luna", path) == record
    assert get_record(ProviderName.OPENAI, "global", "other-model", path) is None
    assert get_record(ProviderName.OPENAI, "other-region", "gpt-5.6-luna", path) is None
    assert "api_key" not in path.read_text(encoding="utf-8").lower()
    with pytest.raises(ValueError, match="VERIFIED"):
        replace(record, fixture_passed=1)
    with pytest.raises(ValueError, match="VERIFIED"):
        replace(record, returned_model="another-model")


def test_one_connection_never_counts_as_verified() -> None:
    from course2career.permissions import Plan, Principal, Role

    client = FakeClient()
    result = check_connection(
        SimpleNamespace(create=lambda *_args, **_kwargs: client),
        Principal(role=Role.DEVELOPER, plan=Plan.DEVELOPER, user_id="test"),
        ProviderName.OPENAI,
        client.model_name,
    )
    assert result.auth_ok and result.request_ok and result.schema_ok and result.usage_ok
    assert result.verification == Verification.SCHEMA_COMPATIBLE
    assert model_capability(ProviderName.OPENAI, "other-model").verification == (
        Verification.UNKNOWN
    )


def test_valid_request_with_invalid_schema_is_connected_only() -> None:
    from course2career.permissions import Plan, Principal, Role

    class InvalidClient:
        model_name = "vendor-model"
        last_usage = LLMUsage(input_tokens=12, output_tokens=4, model="vendor-model")

        def extract_job_skills(self, _jd: str) -> JobAnalysis:
            raise ValueError("private raw response")

    result = check_connection(
        SimpleNamespace(create=lambda *_args, **_kwargs: InvalidClient()),
        Principal(role=Role.DEVELOPER, plan=Plan.DEVELOPER, user_id="test"),
        ProviderName.MOONSHOT,
        "vendor-model",
    )
    assert result.auth_ok and result.request_ok and not result.schema_ok
    assert result.verification == Verification.CONNECTED
    assert result.error_code == ProviderErrorCode.SCHEMA_VALIDATION_FAILED
    assert "private raw response" not in str(result)


def test_full_suite_verifies_only_exact_model() -> None:
    client = FakeClient()
    fixtures = load_fixtures()
    record = validate_provider(
        ProviderName.OPENAI, client.model_name, "global", client, fixtures
    )
    assert record.result == Verification.VERIFIED
    assert record.fixture_passed == len(fixtures)
    assert record.external_calls == 1 + len(fixtures)
    assert record.usage_available and record.cost_available
    assert record.approximate_cost_usd is not None
    assert record.returned_model == client.model_name
    assert client.calls == record.external_calls


def test_absent_usage_and_fixture_failure_cannot_verify() -> None:
    fixtures = load_fixtures()
    no_usage = FakeClient(usage=False)
    record = validate_provider(
        ProviderName.OPENAI, no_usage.model_name, "global", no_usage, fixtures
    )
    assert record.result == Verification.SCHEMA_COMPATIBLE
    assert record.external_calls == 1
    assert not record.usage_available
    assert not record.cost_available
    failing = FakeClient(fail_at=2)
    record = validate_provider(
        ProviderName.OPENAI, failing.model_name, "global", failing, fixtures
    )
    assert record.result == Verification.SCHEMA_COMPATIBLE
    assert record.external_calls == 2
    assert record.error_code == ProviderErrorCode.TIMEOUT


def test_openrouter_prompt_only_cannot_become_verified() -> None:
    client = FakeClient()
    record = validate_provider(
        ProviderName.OPENROUTER,
        client.model_name,
        "global",
        client,
        load_fixtures(),
    )
    assert record.fixture_passed == record.fixture_count
    assert record.result == Verification.SCHEMA_COMPATIBLE
    assert not record.cost_available


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ProviderErrorCode.AUTH_ERROR),
        (404, ProviderErrorCode.MODEL_NOT_FOUND),
        (429, ProviderErrorCode.RATE_LIMIT),
        (400, ProviderErrorCode.SCHEMA_UNSUPPORTED),
        (500, ProviderErrorCode.PROVIDER_ERROR),
    ],
)
def test_http_error_classification_never_exposes_message(
    status: int, expected: ProviderErrorCode
) -> None:
    error = RuntimeError("fake-private-secret")
    error.status_code = status  # type: ignore[attr-defined]
    result = classify_provider_error(error, schema_requested=True)
    assert result.code == expected
    assert result.http_status == status
    assert "fake-private-secret" not in result.sanitized_message
