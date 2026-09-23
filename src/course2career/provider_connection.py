"""用合成 JD 验证协议、提取与 JobAnalysis 契约。"""

from dataclasses import dataclass
from time import monotonic

from course2career.llm_provider import ProviderName
from course2career.models import JobAnalysis
from course2career.permissions import Permission, Principal, authorize
from course2career.provider_factory import LLMProviderFactory

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
        cause = exc.__cause__
        status = getattr(cause, "status_code", None)
        return ConnectionTestResult(
            provider,
            client.model_name if client is not None else model,
            False if status in {401, 403} else None,
            False,
            False,
            client is not None and client.last_usage is not None,
            round((monotonic() - started) * 1000),
            "连接测试未通过，请检查 Key、端点与模型配置。",
        )
