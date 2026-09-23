"""用合成 JD 验证协议、提取与 JobAnalysis 契约。"""

from dataclasses import dataclass
from time import monotonic

from course2career.llm_provider import ProviderName
from course2career.models import JobAnalysis
from course2career.permissions import Permission, Principal, authorize
from course2career.provider_error_classification import classify_provider_error
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_registry import get_provider_preset
from course2career.provider_verification import ProviderErrorCode, Verification
from course2career.structured_output import StructuredOutputStrategy

SYNTHETIC_JD = (
    "合成测试岗位：数据分析实习生。任职要求：熟悉 Python 和 SQL，"
    "能够整理表格数据并说明分析依据。"
)


@dataclass(frozen=True)
class ConnectionTestResult:
    provider: ProviderName
    model: str
    auth_ok: bool | None
    request_ok: bool
    schema_ok: bool
    usage_available: bool
    latency_ms: int
    sanitized_error: str | None
    error_code: ProviderErrorCode | None = None
    http_status: int | None = None

    @property
    def usage_ok(self) -> bool:
        return self.usage_available

    @property
    def verification(self) -> Verification:
        if self.schema_ok:
            return Verification.SCHEMA_COMPATIBLE
        if self.request_ok:
            return Verification.CONNECTED
        return Verification.UNKNOWN


def test_provider_connection(
    factory: LLMProviderFactory,
    principal: Principal,
    provider: ProviderName,
    model: str,
    endpoint_id: str | None = None,
) -> ConnectionTestResult:
    authorize(principal, Permission.USE_OWN_API_KEY)
    started = monotonic()
    client = None
    try:
        client = factory.create(
            principal,
            provider=provider,
            key_mode="user",
            model=model,
            endpoint_id=endpoint_id,
        )
        result = client.extract_job_skills(SYNTHETIC_JD)
        if not isinstance(result, JobAnalysis):
            raise ValueError("invalid analysis contract")
        return ConnectionTestResult(
            provider,
            client.model_name,
            True,
            True,
            True,
            client.last_usage is not None,
            round((monotonic() - started) * 1000),
            None,
        )
    except Exception as exc:
        preset = get_provider_preset(provider)
        classified = classify_provider_error(
            exc,
            schema_requested=preset.structured_output_strategy
            in {
                StructuredOutputStrategy.STRICT_JSON_SCHEMA,
                StructuredOutputStrategy.NATIVE_SCHEMA,
            },
        )
        usage_available = client is not None and client.last_usage is not None
        request_ok = usage_available or (
            classified.code == ProviderErrorCode.SCHEMA_VALIDATION_FAILED
        )
        return ConnectionTestResult(
            provider,
            client.model_name if client is not None else model,
            False
            if classified.code == ProviderErrorCode.AUTH_ERROR
            else True
            if classified.http_status is not None or request_ok
            else None,
            request_ok,
            False,
            usage_available,
            round((monotonic() - started) * 1000),
            classified.sanitized_message,
            classified.code,
            classified.http_status,
        )
