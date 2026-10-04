"""用合成 JD 验证协议、提取与 JobAnalysis 契约。"""

from dataclasses import dataclass
from time import monotonic

from course2career.llm_provider import ProviderName
from course2career.models import JobAnalysis
from course2career.permissions import Permission, Principal, authorize
from course2career.provider_error_classification import classify_provider_error
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_registry import get_provider_preset
from course2career.provider_runtime import ModelMatch, ModelTrace
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
    model_trace: ModelTrace | None = None
    job_analysis_ok: bool = False

    @property
    def returned_model(self) -> str | None:
        return self.model_trace.returned_model if self.model_trace else None

    @property
    def model_match(self) -> ModelMatch:
        return self.model_trace.model_match if self.model_trace else ModelMatch.UNKNOWN

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
            model_trace=getattr(client, "last_trace", None),
            job_analysis_ok=True,
        )
    except Exception as exc:
        preset = get_provider_preset(provider)
        classified = classify_provider_error(
            exc,
            schema_requested=(
                getattr(client, "structured_strategy", None)
                or preset.strategy_for_model(model)
            )
            in {
                StructuredOutputStrategy.STRICT_JSON_SCHEMA,
                StructuredOutputStrategy.NATIVE_SCHEMA,
            },
        )
        usage_available = client is not None and client.last_usage is not None
        trace = getattr(client, "last_trace", None)
        request_ok = bool(
            trace and trace.attempts and trace.attempts[-1].response_received
        ) or (
            trace is None
            and client is not None
            and (
                usage_available
                or classified.code == ProviderErrorCode.SCHEMA_VALIDATION_FAILED
            )
        )
        return ConnectionTestResult(
            provider,
            client.model_name if client is not None else model,
            False
            if classified.code == ProviderErrorCode.AUTH_ERROR
            else True
            if request_ok
            else None,
            request_ok,
            False,
            usage_available,
            round((monotonic() - started) * 1000),
            classified.sanitized_message,
            classified.code,
            classified.http_status,
            model_trace=trace,
        )
