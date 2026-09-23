"""固定合成 JD 的真实验证编排；仅显式运行脚本时调用外部 API。"""

import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from urllib.request import Request, build_opener

from course2career.config import Settings
from course2career.llm_client import OpenAIJDClient
from course2career.llm_provider import LLMProvider, ProviderName
from course2career.llm_providers import DeepSeekProvider, OpenAICompatibleChatProvider
from course2career.models import JobAnalysis
from course2career.native_providers import (
    AnthropicMessagesProvider,
    GeminiProvider,
    _NoRedirect,
)
from course2career.permissions import Plan, Principal, Role
from course2career.provider_connection import test_provider_connection
from course2career.provider_error_classification import classify_provider_error
from course2career.provider_registry import get_provider_preset
from course2career.provider_verification import (
    ProviderErrorCode,
    Verification,
    VerificationRecord,
    now_utc,
)
from course2career.structured_output import StructuredOutputStrategy

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "provider_validation"
    / "cases.json"
)

_COST_RATES: dict[tuple[ProviderName, str], tuple[float, float, str]] = {
    (ProviderName.OPENAI, "gpt-5.6-luna"): (
        0.20,
        1.20,
        "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
    ),
    (ProviderName.ANTHROPIC, "claude-haiku-4-5-20251001"): (
        1.00,
        5.00,
        "https://platform.claude.com/docs/en/about-claude/pricing",
    ),
}


@dataclass(frozen=True)
class ValidationFixture:
    id: str
    jd: str
    must_include: tuple[str, ...]
    must_exclude: tuple[str, ...]


def load_fixtures(path: Path = FIXTURE_PATH) -> tuple[ValidationFixture, ...]:
    return tuple(
        ValidationFixture(
            id=item["id"],
            jd=item["jd"],
            must_include=tuple(item["must_include"]),
            must_exclude=tuple(item["must_exclude"]),
        )
        for item in json.loads(path.read_text(encoding="utf-8"))
    )


def fixture_passes(fixture: ValidationFixture, result: JobAnalysis) -> bool:
    if not isinstance(result, JobAnalysis) or not result.skills:
        return False
    names = [
        f"{skill.name} {skill.normalized_name}".casefold() for skill in result.skills
    ]
    if any(
        not any(term.casefold() in name for name in names)
        for term in fixture.must_include
    ):
        return False
    if any(
        any(term.casefold() in name for name in names) for term in fixture.must_exclude
    ):
        return False
    return all(
        skill.evidence_text.strip() and skill.evidence_text.strip() in fixture.jd
        for skill in result.skills
    )


def build_validation_client(
    provider: ProviderName,
    model: str,
    endpoint_id: str,
    api_key: str,
    *,
    openrouter_schema_supported: bool = False,
) -> LLMProvider:
    """使用生产适配器，关闭 SDK 自动重试以限制真实请求数量。"""
    from openai import DefaultHttpxClient, OpenAI

    preset = get_provider_preset(provider)
    endpoint = preset.endpoint(endpoint_id)
    if provider == ProviderName.OPENAI:
        sdk = OpenAI(
            api_key=api_key,
            timeout=30,
            max_retries=0,
            http_client=DefaultHttpxClient(follow_redirects=False),
        )
        return OpenAIJDClient(
            Settings(openai_api_key=api_key, openai_model=model),
            sdk_client=sdk,
            max_output_tokens=600,
        )
    if provider == ProviderName.DEEPSEEK:
        sdk = OpenAI(
            api_key=api_key,
            base_url=endpoint,
            timeout=30,
            max_retries=0,
            http_client=DefaultHttpxClient(follow_redirects=False),
        )
        return DeepSeekProvider(
            api_key=api_key,
            model=model,
            fallback_models=(),
            max_output_tokens=600,
            sdk_client=sdk,
        )
    if provider in {ProviderName.ANTHROPIC, ProviderName.GEMINI}:
        native_type = (
            AnthropicMessagesProvider
            if provider == ProviderName.ANTHROPIC
            else GeminiProvider
        )
        return native_type(
            preset=preset,
            api_key=api_key,
            model=model,
            endpoint_id=endpoint_id,
            max_output_tokens=600,
        )
    sdk = OpenAI(
        api_key=api_key,
        base_url=endpoint,
        timeout=30,
        max_retries=0,
        http_client=DefaultHttpxClient(follow_redirects=False),
    )
    return OpenAICompatibleChatProvider(
        preset=preset,
        api_key=api_key,
        model=model,
        endpoint_id=endpoint_id,
        sdk_client=sdk,
        max_output_tokens=600,
        structured_strategy=(
            StructuredOutputStrategy.STRICT_JSON_SCHEMA
            if provider == ProviderName.OPENROUTER and openrouter_schema_supported
            else None
        ),
    )


def openrouter_supports_schema(model: str, api_key: str) -> bool:
    """只信精确模型的官方 metadata；不缓存、不记录响应原文。"""
    request = Request(
        "https://openrouter.ai/api/v1/models?supported_parameters=response_format",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with build_opener(_NoRedirect).open(request, timeout=15) as response:
        payload = response.read(10_000_001)
    if len(payload) > 10_000_000:
        return False
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        return False
    return any(
        item.get("id") == model
        and "response_format" in item.get("supported_parameters", [])
        for item in parsed.get("data", [])
        if isinstance(item, dict)
    )


def validate_provider(
    provider: ProviderName,
    model: str,
    endpoint_id: str,
    client: LLMProvider,
    fixtures: tuple[ValidationFixture, ...],
) -> VerificationRecord:
    preset = get_provider_preset(provider)
    strategy = getattr(
        client, "structured_strategy", None
    ) or preset.strategy_for_model(model)
    principal = Principal(
        role=Role.DEVELOPER, plan=Plan.DEVELOPER, user_id="validation"
    )
    factory = SimpleNamespace(create=lambda *_args, **_kwargs: client)
    started = monotonic()
    calls = 1
    passed = 0
    input_tokens = 0
    output_tokens = 0
    usage_count = 0
    returned_model: str | None = None
    model_consistent = True
    error_code: ProviderErrorCode | None = None
    http_status: int | None = None
    connection = test_provider_connection(
        factory, principal, provider, model, endpoint_id
    )
    if client.last_usage is not None:
        input_tokens += client.last_usage.input_tokens
        output_tokens += client.last_usage.output_tokens
        usage_count += 1
        returned_model = client.last_usage.model
        model_consistent = returned_model == model
    if connection.schema_ok:
        result = Verification.SCHEMA_COMPATIBLE
    elif connection.request_ok:
        result = Verification.CONNECTED
    elif connection.error_code == ProviderErrorCode.SCHEMA_UNSUPPORTED:
        result = Verification.UNSUPPORTED
    else:
        result = Verification.UNKNOWN
    error_code = connection.error_code
    http_status = connection.http_status
    if connection.schema_ok and connection.usage_ok:
        for fixture in fixtures:
            calls += 1
            try:
                analysis = client.extract_job_skills(fixture.jd)
                if client.last_usage is not None:
                    input_tokens += client.last_usage.input_tokens
                    output_tokens += client.last_usage.output_tokens
                    usage_count += 1
                    returned_model = client.last_usage.model
                    model_consistent = model_consistent and returned_model == model
                if not fixture_passes(fixture, analysis):
                    error_code = ProviderErrorCode.SCHEMA_VALIDATION_FAILED
                    break
                passed += 1
            except Exception as exc:
                classified = classify_provider_error(
                    exc,
                    schema_requested=strategy
                    in {
                        StructuredOutputStrategy.STRICT_JSON_SCHEMA,
                        StructuredOutputStrategy.NATIVE_SCHEMA,
                    },
                )
                error_code = classified.code
                http_status = classified.http_status
                break
        if (
            passed == len(fixtures)
            and len(fixtures) >= 3
            and usage_count == calls
            and model_consistent
            and (
                provider != ProviderName.OPENROUTER
                or strategy == StructuredOutputStrategy.STRICT_JSON_SCHEMA
            )
        ):
            result = Verification.VERIFIED
            error_code = None
    rates = _COST_RATES.get((provider, model))
    cost_available = rates is not None and usage_count == calls
    cost = (
        round((input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000, 8)
        if cost_available and rates is not None
        else None
    )
    return VerificationRecord(
        provider=provider,
        endpoint_id=endpoint_id,
        model=model,
        protocol=preset.primary_protocol,
        schema_strategy=strategy,
        verified_at=now_utc(),
        fixture_count=len(fixtures),
        fixture_passed=passed,
        latency_ms=round((monotonic() - started) * 1000),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usage_available=usage_count == calls,
        cost_available=cost_available,
        result=result,
        error_code=error_code,
        http_status=http_status,
        external_calls=calls,
        approximate_cost_usd=cost,
        cost_source=rates[2] if cost_available and rates is not None else None,
        returned_model=returned_model,
    )
