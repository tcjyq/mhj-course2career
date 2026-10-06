"""Runtime-only identity and normalized JobAnalysis results; no secrets or JD text."""

from dataclasses import dataclass, replace
from enum import StrEnum

from course2career.llm_provider import LLMUsage, ProviderName
from course2career.models import JobAnalysis


class ModelMatch(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


def returned_model_id(value: object) -> str | None:
    """Preserve unfamiliar IDs exactly; never truncate or substitute a request ID."""
    if isinstance(value, str) and value.strip() and len(value) <= 200:
        return value if value.isprintable() else None
    return None


@dataclass(frozen=True)
class ModelAttempt:
    requested_model: str
    returned_model: str | None = None
    success: bool = False
    response_received: bool = False
    error_code: str | None = None
    fallback_reason: str | None = None

    @property
    def model_match(self) -> ModelMatch:
        if self.returned_model is None:
            return ModelMatch.UNKNOWN
        return (
            ModelMatch.MATCH
            if self.returned_model == self.requested_model
            else ModelMatch.MISMATCH
        )


@dataclass(frozen=True)
class ModelTrace:
    saved_model: str
    resolved_model: str
    attempts: tuple[ModelAttempt, ...] = ()
    displayed_model: str | None = None

    @property
    def returned_model(self) -> str | None:
        return self.attempts[-1].returned_model if self.attempts else None

    @property
    def model_match(self) -> ModelMatch:
        return self.attempts[-1].model_match if self.attempts else ModelMatch.UNKNOWN

    def proves_exact_model(self, model: str) -> bool:
        # A successful fallback does not certify the originally requested model.
        return bool(self.attempts) and all(
            attempt.success
            and attempt.response_received
            and attempt.requested_model == model
            and attempt.returned_model == model
            for attempt in self.attempts
        )


@dataclass(frozen=True)
class AttemptBudget:
    """One wire attempt, or the existing DeepSeek 404 fallback (at most two)."""

    max_attempts: int = 1

    def __post_init__(self) -> None:
        if self.max_attempts not in {1, 2}:
            raise ValueError("Unsupported provider attempt budget")

    def allows(self, attempts_used: int) -> bool:
        return 0 <= attempts_used < self.max_attempts


@dataclass(frozen=True)
class CallEvidence:
    schema_ok: bool
    job_analysis_ok: bool
    usage_ok: bool
    model_match: ModelMatch


@dataclass(frozen=True)
class ProviderCallResult:
    analysis: JobAnalysis
    usage: LLMUsage | None
    model_trace: ModelTrace
    provider: ProviderName
    endpoint: str
    verification: CallEvidence


class ProviderRuntime:
    """Shared bookkeeping; adapters retain their existing wire implementations."""

    def _init_runtime(
        self,
        saved_model: str,
        resolved_model: str,
        endpoint: str,
        *,
        max_attempts: int = 1,
    ) -> None:
        self._saved_model = saved_model
        self.endpoint = endpoint
        self.attempt_budget = AttemptBudget(max_attempts)
        self._last_trace = ModelTrace(saved_model, resolved_model)
        self._last_result: ProviderCallResult | None = None

    @property
    def last_trace(self) -> ModelTrace:
        return self._last_trace

    @property
    def last_result(self) -> ProviderCallResult | None:
        return self._last_result

    def _begin_call(self, requested_model: str) -> None:
        self._last_usage = None
        self._last_result = None
        self._last_trace = ModelTrace(self._saved_model, requested_model)
        self._start_attempt(requested_model)

    def _start_attempt(
        self, requested_model: str, fallback_reason: str | None = None
    ) -> None:
        if not self.attempt_budget.allows(len(self._last_trace.attempts)):
            raise RuntimeError("Provider attempt budget exhausted")
        self._last_trace = replace(
            self._last_trace,
            attempts=(
                *self._last_trace.attempts,
                ModelAttempt(requested_model, fallback_reason=fallback_reason),
            ),
        )

    def _observe_response(self, model: object) -> None:
        self._update_attempt(
            returned_model=returned_model_id(model), response_received=True
        )

    def _update_attempt(self, **changes: object) -> None:
        attempts = self._last_trace.attempts
        self._last_trace = replace(
            self._last_trace,
            attempts=(
                *attempts[:-1],
                replace(attempts[-1], **changes),
            ),
        )

    def _fail_attempt(
        self, exc: BaseException, *, schema_requested: bool = False
    ) -> None:
        from course2career.provider_error_classification import classify_provider_error

        self._update_attempt(
            success=False,
            error_code=classify_provider_error(
                exc, schema_requested=schema_requested
            ).code.value,
        )

    def _finish_call(self, analysis: JobAnalysis) -> JobAnalysis:
        self._update_attempt(success=True)
        usage = self._last_usage
        self._last_trace = replace(
            self._last_trace,
            displayed_model=(
                usage.model
                if usage is not None
                else self._last_trace.attempts[-1].requested_model
            ),
        )
        self._last_result = ProviderCallResult(
            analysis,
            usage,
            self._last_trace,
            self.provider_name,
            self.endpoint,
            CallEvidence(True, True, usage is not None, self._last_trace.model_match),
        )
        return analysis
