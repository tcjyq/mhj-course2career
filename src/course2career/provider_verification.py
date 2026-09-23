"""仅本机使用的模型验证证据；不包含凭证、请求正文或原始响应。"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from course2career.llm_provider import ProviderName
from course2career.provider_registry import ProviderProtocol
from course2career.structured_output import StructuredOutputStrategy

DEFAULT_RECORD_PATH = (
    Path(__file__).resolve().parents[2]
    / "outputs"
    / "c08-provider-validation"
    / "records.json"
)


class Verification(StrEnum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    SCHEMA_COMPATIBLE = "schema_compatible"
    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"


class ProviderErrorCode(StrEnum):
    AUTH_ERROR = "AUTH_ERROR"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    SCHEMA_UNSUPPORTED = "SCHEMA_UNSUPPORTED"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass(frozen=True)
class VerificationRecord:
    provider: ProviderName
    endpoint_id: str
    model: str
    protocol: ProviderProtocol
    schema_strategy: StructuredOutputStrategy
    verified_at: str
    fixture_count: int
    fixture_passed: int
    latency_ms: int
    input_tokens: int
    output_tokens: int
    usage_available: bool
    cost_available: bool
    result: Verification
    error_code: ProviderErrorCode | None = None
    http_status: int | None = None
    external_calls: int = 0
    approximate_cost_usd: float | None = None
    cost_source: str | None = None
    returned_model: str | None = None

    def __post_init__(self) -> None:
        if self.result == Verification.VERIFIED and (
            self.fixture_count < 3
            or self.fixture_passed != self.fixture_count
            or not self.usage_available
            or self.external_calls < self.fixture_count + 1
            or self.returned_model != self.model
            or self.error_code is not None
        ):
            raise ValueError("VERIFIED 需要完整 fixture 与 usage 证据")


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _record_key(provider: ProviderName, endpoint_id: str, model: str) -> str:
    return json.dumps([provider.value, endpoint_id, model], ensure_ascii=False)


def load_records(path: Path = DEFAULT_RECORD_PATH) -> dict[str, VerificationRecord]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        records = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            try:
                record = VerificationRecord(
                    **{
                        **value,
                        "provider": ProviderName(value["provider"]),
                        "protocol": ProviderProtocol(value["protocol"]),
                        "schema_strategy": StructuredOutputStrategy(
                            value["schema_strategy"]
                        ),
                        "result": Verification(value["result"]),
                        "error_code": ProviderErrorCode(value["error_code"])
                        if value.get("error_code")
                        else None,
                    }
                )
                if key == _record_key(
                    record.provider, record.endpoint_id, record.model
                ):
                    records[key] = record
            except (KeyError, TypeError, ValueError):
                continue
        return records
    except (OSError, ValueError):
        return {}


def get_record(
    provider: ProviderName,
    endpoint_id: str,
    model: str,
    path: Path = DEFAULT_RECORD_PATH,
) -> VerificationRecord | None:
    return load_records(path).get(_record_key(provider, endpoint_id, model))


def save_record(record: VerificationRecord, path: Path = DEFAULT_RECORD_PATH) -> None:
    records = load_records(path)
    records[_record_key(record.provider, record.endpoint_id, record.model)] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(".tmp")
    staged.write_text(
        json.dumps(
            {key: asdict(value) for key, value in records.items()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    staged.replace(path)
