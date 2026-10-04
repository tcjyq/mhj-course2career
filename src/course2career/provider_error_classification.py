"""只读取异常类型与 HTTP 状态，不保存可能泄露凭证的异常文本。"""

from dataclasses import dataclass
from json import JSONDecodeError
from urllib.error import HTTPError, URLError

from pydantic import ValidationError

from course2career.provider_verification import ProviderErrorCode


@dataclass(frozen=True)
class ClassifiedProviderError:
    code: ProviderErrorCode
    http_status: int | None
    sanitized_message: str


_MESSAGES = {
    ProviderErrorCode.AUTH_ERROR: "API Key 鉴权失败，请检查凭证与区域。",
    ProviderErrorCode.MODEL_NOT_FOUND: "模型 ID 不存在或当前账户无权使用。",
    ProviderErrorCode.RATE_LIMIT: "供应商限流或额度不足。",
    ProviderErrorCode.TIMEOUT: "供应商请求超时。",
    ProviderErrorCode.SCHEMA_UNSUPPORTED: "当前模型不接受请求的结构化输出格式。",
    ProviderErrorCode.SCHEMA_VALIDATION_FAILED: "返回内容不符合 JobAnalysis 结构。",
    ProviderErrorCode.FIXTURE_ASSERTION_FAILED: "固定验证集断言未通过。",
    ProviderErrorCode.PROVIDER_ERROR: "供应商请求失败，请检查模型与端点配置。",
    ProviderErrorCode.NETWORK_ERROR: "网络连接失败。",
    ProviderErrorCode.UNKNOWN_ERROR: "连接测试未通过。",
    ProviderErrorCode.MODEL_NOT_INCLUDED: "当前凭证未包含此模型的访问权限。",
    ProviderErrorCode.USAGE_LIMIT: "当前凭证的使用额度已达上限。",
    ProviderErrorCode.QUOTA_EXHAUSTED: "供应商账户额度已耗尽。",
    ProviderErrorCode.PROVIDER_UNAVAILABLE: "供应商暂时不可用。",
}


def classify_provider_error(
    exc: BaseException, *, schema_requested: bool = False
) -> ClassifiedProviderError:
    causes = []
    current: BaseException | None = exc
    while current is not None and len(causes) < 5:
        causes.append(current)
        current = current.__cause__
    status = next(
        (
            code
            for item in causes
            if isinstance(code := getattr(item, "status_code", None), int)
        ),
        None,
    )
    if status is None:
        status = next(
            (item.code for item in causes if isinstance(item, HTTPError)), None
        )
    # Read only an allowlisted SDK code, never error text or raw response bodies.
    explicit = next(
        (
            value
            for item in causes
            if isinstance(value := getattr(item, "code", None), str)
            and value
            in {
                "insufficient_quota",
                "quota_exceeded",
                "usage_limit_reached",
                "model_not_included",
                "unsupported_response_format",
                "unsupported_json_schema",
            }
        ),
        None,
    )
    if explicit in {"insufficient_quota", "quota_exceeded"}:
        code = ProviderErrorCode.QUOTA_EXHAUSTED
    elif explicit == "usage_limit_reached":
        code = ProviderErrorCode.USAGE_LIMIT
    elif explicit == "model_not_included":
        code = ProviderErrorCode.MODEL_NOT_INCLUDED
    elif status in {401, 403}:
        code = ProviderErrorCode.AUTH_ERROR
    elif status == 404:
        code = ProviderErrorCode.MODEL_NOT_FOUND
    elif status == 429:
        code = ProviderErrorCode.RATE_LIMIT
    elif (
        status == 400
        and schema_requested
        and explicit in {"unsupported_response_format", "unsupported_json_schema"}
    ):
        code = ProviderErrorCode.SCHEMA_UNSUPPORTED
    elif any(isinstance(item, (TimeoutError,)) for item in causes) or any(
        "Timeout" in type(item).__name__ for item in causes
    ):
        code = ProviderErrorCode.TIMEOUT
    elif any(
        isinstance(item, (ValidationError, JSONDecodeError, ValueError))
        for item in causes
    ):
        code = ProviderErrorCode.SCHEMA_VALIDATION_FAILED
    elif any(isinstance(item, (ConnectionError, URLError)) for item in causes) or any(
        "ConnectionError" in type(item).__name__ for item in causes
    ):
        code = ProviderErrorCode.NETWORK_ERROR
    elif status is not None and status >= 500:
        code = ProviderErrorCode.PROVIDER_UNAVAILABLE
    elif status is not None:
        code = ProviderErrorCode.PROVIDER_ERROR
    else:
        code = ProviderErrorCode.UNKNOWN_ERROR
    return ClassifiedProviderError(code, status, _MESSAGES[code])
