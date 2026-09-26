"""B2 的本地确定性测试，不调用外部 API。"""

import json
import sys
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
    diagnose_fixture,
    fixture_passes,
    load_fixtures,
    save_fixture_diagnostics,
    validate_provider,
)
from course2career.provider_verification import (
    CERTIFIED_RECORD_PATH,
    ProviderErrorCode,
    Verification,
    VerificationRecord,
    get_record,
    load_records,
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


def _analysis_with_skills(
    *names: str, invalid_evidence: str | None = None
) -> JobAnalysis:
    return JobAnalysis(
        skills=[
            JobSkill(
                name=name,
                normalized_name=name,
                category="技术",
                evidence_text="非原文" if name == invalid_evidence else name,
            )
            for name in names
        ]
    )


@pytest.mark.parametrize("missing", ["Python", "SQL", "需求分析"])
def test_fixture_diagnostic_identifies_each_missing_term(missing: str) -> None:
    fixture = load_fixtures()[1]
    names = (name for name in fixture.must_include if name != missing)
    diagnosis = diagnose_fixture(fixture, _analysis_with_skills(*names))
    assert not diagnosis.passed
    assert diagnosis.missing_required_terms == (missing,)
    assert diagnosis.present_forbidden_terms == ()
    assert diagnosis.invalid_evidence_skill_names == ()
    assert diagnosis.skill_count == 2
    assert not fixture_passes(fixture, _analysis_with_skills(*names))


def test_fixture_diagnostic_identifies_non_verbatim_evidence() -> None:
    fixture = load_fixtures()[1]
    analysis = _analysis_with_skills(*fixture.must_include, invalid_evidence="SQL")
    diagnosis = diagnose_fixture(fixture, analysis)
    assert not diagnosis.passed
    assert diagnosis.missing_required_terms == ()
    assert diagnosis.invalid_evidence_skill_names == ("SQL",)
    assert not fixture_passes(fixture, analysis)


def test_fixture_diagnostic_accepts_exact_evidence() -> None:
    fixture = load_fixtures()[1]
    analysis = _analysis_with_skills(*fixture.must_include)
    diagnosis = diagnose_fixture(fixture, analysis)
    assert diagnosis.passed
    assert diagnosis.skill_count == 3
    assert not diagnosis.invalid_evidence_skill_names
    assert fixture_passes(fixture, analysis)


def test_fixture_diagnostic_identifies_forbidden_java() -> None:
    fixture = load_fixtures()[3]
    analysis = _analysis_with_skills("Python", "Java")
    diagnosis = diagnose_fixture(fixture, analysis)
    assert not diagnosis.passed
    assert diagnosis.present_forbidden_terms == ("Java",)
    assert diagnosis.invalid_evidence_skill_names == ()
    assert not fixture_passes(fixture, analysis)


def test_fixture_diagnostic_keeps_unknown_skill_names_out_of_file(
    tmp_path: Path,
) -> None:
    fixture = load_fixtures()[1]
    analysis = _analysis_with_skills("Python", "SQL", "需求分析", "private-secret")
    diagnosis = diagnose_fixture(fixture, analysis)
    assert diagnosis.invalid_evidence_skill_names == ("skill_4",)
    path = tmp_path / "fixture_diagnostics.json"
    save_fixture_diagnostics(
        ProviderName.BAILIAN, "cn-beijing", "qwen3.8-flash", [diagnosis], path
    )
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert set(saved[0]) == {
        "provider",
        "endpoint_id",
        "model",
        "fixture_id",
        "passed",
        "missing_required_terms",
        "present_forbidden_terms",
        "invalid_evidence_skill_names",
    }
    assert fixture.jd not in path.read_text(encoding="utf-8")
    assert "private-secret" not in path.read_text(encoding="utf-8")
    path.write_text(
        json.dumps([{**saved[0], "raw_response": "private-secret"}]),
        encoding="utf-8",
    )
    save_fixture_diagnostics(ProviderName.OPENAI, "global", "gpt-test", [], path)
    assert "raw_response" not in path.read_text(encoding="utf-8")
    assert "private-secret" not in path.read_text(encoding="utf-8")
    save_fixture_diagnostics(
        ProviderName.BAILIAN, "cn-beijing", "qwen3.8-flash", [], path
    )
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_fixture_assertion_failure_is_not_schema_failure() -> None:
    class MissingTermClient(FakeClient):
        def extract_job_skills(self, jd: str) -> JobAnalysis:
            analysis = super().extract_job_skills(jd)
            if self.calls == 3:
                return analysis.model_copy(
                    update={
                        "skills": [
                            skill for skill in analysis.skills if skill.name != "SQL"
                        ]
                    }
                )
            return analysis

    client = MissingTermClient()
    diagnostics = []
    record = validate_provider(
        ProviderName.OPENAI,
        client.model_name,
        "global",
        client,
        load_fixtures(),
        diagnostics=diagnostics,
    )
    assert record.result == Verification.SCHEMA_COMPATIBLE
    assert record.error_code == ProviderErrorCode.FIXTURE_ASSERTION_FAILED
    assert record.fixture_passed == 1
    assert record.external_calls == 3
    assert [item.fixture_id for item in diagnostics] == [
        "case_01_simple",
        "case_02_multiple",
    ]
    assert diagnostics[0].passed
    assert diagnostics[1].missing_required_terms == ("SQL",)


def test_fixture_parse_failure_keeps_schema_error_separate() -> None:
    class InvalidFixtureClient(FakeClient):
        def extract_job_skills(self, jd: str) -> JobAnalysis:
            if self.calls == 2:
                self.calls += 1
                raise ValueError("private raw model response")
            return super().extract_job_skills(jd)

    client = InvalidFixtureClient()
    diagnostics = []
    record = validate_provider(
        ProviderName.OPENAI,
        client.model_name,
        "global",
        client,
        load_fixtures(),
        diagnostics=diagnostics,
    )
    assert record.error_code == ProviderErrorCode.SCHEMA_VALIDATION_FAILED
    assert [item.fixture_id for item in diagnostics] == ["case_01_simple"]
    assert "private raw model response" not in str(record)


def test_validation_script_persists_sanitized_fixture_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import validate_provider as script

    class OfflineClient(FakeClient):
        model_name = "qwen3.8-flash"

        def extract_job_skills(self, jd: str) -> JobAnalysis:
            analysis = super().extract_job_skills(jd)
            if self.calls == 3:
                return analysis.model_copy(
                    update={
                        "skills": [
                            skill for skill in analysis.skills if skill.name != "SQL"
                        ]
                    }
                )
            return analysis

    path = tmp_path / "fixture_diagnostics.json"
    saved_records = []
    monkeypatch.setenv("BAILIAN_API_KEY", "fake-key-never-sent")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_provider.py",
            "--provider",
            "bailian",
            "--endpoint-id",
            "cn-beijing",
            "--model",
            "qwen3.8-flash",
        ],
    )
    monkeypatch.setattr(
        script, "build_validation_client", lambda *_args, **_kwargs: OfflineClient()
    )
    monkeypatch.setattr(script, "save_record", saved_records.append)
    monkeypatch.setattr(script, "SUMMARY_PATH", tmp_path / "summary.md")
    monkeypatch.setattr(script, "DIAGNOSTIC_PATH", path)
    monkeypatch.setattr(
        script,
        "save_fixture_diagnostics",
        lambda provider, endpoint, model, diagnostics: save_fixture_diagnostics(
            provider, endpoint, model, diagnostics, path
        ),
    )
    assert script.main() == 0
    assert saved_records[0].error_code == ProviderErrorCode.FIXTURE_ASSERTION_FAILED
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert rows[0]["passed"]
    assert rows[1]["missing_required_terms"] == ["SQL"]
    assert "fake-key-never-sent" not in path.read_text(encoding="utf-8")
    assert load_fixtures()[1].jd not in path.read_text(encoding="utf-8")


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


def test_certified_mainland_records_bind_exact_models_and_endpoints() -> None:
    records = load_records(CERTIFIED_RECORD_PATH)
    expected = {
        (ProviderName.BAILIAN, "cn-beijing", "qwen3.8-flash"),
        (ProviderName.DEEPSEEK, "global", "deepseek-flash"),
    }
    assert {
        (record.provider, record.endpoint_id, record.model)
        for record in records.values()
    } == expected
    for provider, endpoint_id, model in expected:
        record = get_record(provider, endpoint_id, model)
        assert record is not None
        assert record.result == Verification.VERIFIED
        assert record.fixture_count == record.fixture_passed == 4
        assert record.usage_available and record.external_calls == 5
        assert record.returned_model == model and record.error_code is None
        assert get_record(provider, "other-region", model) is None
        assert get_record(provider, endpoint_id, "other-model") is None
    assert get_record(ProviderName.SILICONFLOW, "cn", "qwen3.8-flash") is None


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
