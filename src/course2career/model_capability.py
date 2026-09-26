"""模型级官方元数据与 Course2Career 验证证据保持独立。"""

from dataclasses import dataclass
from enum import StrEnum

from course2career.llm_provider import ProviderName
from course2career.provider_registry import get_provider_preset
from course2career.provider_verification import Verification, get_record
from course2career.structured_output import StructuredOutputStrategy


class CapabilitySupport(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class LifecycleStatus(StrEnum):
    CURRENT = "current"
    DEPRECATED = "deprecated"
    COMPATIBILITY_ALIAS = "compatibility_alias"
    RETIRED = "retired"
    UNKNOWN = "unknown"


class ModelStatus(StrEnum):
    DISCOVERED = "discovered"
    CAPABILITY_ELIGIBLE = "capability_eligible"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"
    DEPRECATED = "deprecated"
    COMPATIBILITY_ALIAS = "compatibility_alias"
    RETIRED = "retired"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PricingMetadata:
    input_price: float | None = None
    output_price: float | None = None
    cached_input_price: float | None = None
    currency: str | None = None
    unit: str | None = None
    source: str | None = None
    checked_at: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ModelCapability:
    provider_id: ProviderName
    model_id: str
    structured_output: CapabilitySupport
    reasoning: CapabilitySupport
    verification: Verification
    structured_output_strategy: StructuredOutputStrategy
    endpoint_id: str = ""
    display_name: str | None = None
    text_generation: CapabilitySupport = CapabilitySupport.UNKNOWN
    context_window: int | None = None
    max_output_tokens: int | None = None
    pricing: PricingMetadata = PricingMetadata()
    availability_source: str | None = None
    capability_source: str | None = None
    source_url: str | None = None
    discovered_at: str | None = None
    checked_at: str | None = None
    verified_at: str | None = None
    lifecycle_status: LifecycleStatus = LifecycleStatus.UNKNOWN
    replacement_model: str | None = None

    @property
    def verification_status(self) -> Verification:
        return self.verification

    @property
    def status(self) -> ModelStatus:
        if self.lifecycle_status == LifecycleStatus.RETIRED:
            return ModelStatus.RETIRED
        if self.lifecycle_status == LifecycleStatus.COMPATIBILITY_ALIAS:
            return ModelStatus.COMPATIBILITY_ALIAS
        if self.lifecycle_status == LifecycleStatus.DEPRECATED:
            return ModelStatus.DEPRECATED
        if self.verification == Verification.VERIFIED:
            return ModelStatus.VERIFIED
        if self.verification == Verification.UNSUPPORTED:
            return ModelStatus.UNSUPPORTED
        if self.text_generation == CapabilitySupport.UNSUPPORTED:
            return ModelStatus.UNSUPPORTED
        if self.structured_output == CapabilitySupport.SUPPORTED:
            return ModelStatus.CAPABILITY_ELIGIBLE
        if self.text_generation == CapabilitySupport.SUPPORTED:
            return ModelStatus.UNVERIFIED
        if self.availability_source:
            return ModelStatus.DISCOVERED
        return ModelStatus.UNKNOWN

    @property
    def input_price(self) -> float | None:
        return self.pricing.input_price

    @property
    def output_price(self) -> float | None:
        return self.pricing.output_price

    @property
    def cached_input_price(self) -> float | None:
        return self.pricing.cached_input_price

    @property
    def currency(self) -> str | None:
        return self.pricing.currency

    @property
    def price_unit(self) -> str | None:
        return self.pricing.unit

    @property
    def pricing_source(self) -> str | None:
        return self.pricing.source


def model_capability(
    provider: ProviderName, model: str, endpoint_id: str | None = None
) -> ModelCapability:
    """无目录时仅返回 B2 证据；不能从预设推断官方模型能力。"""
    preset = get_provider_preset(provider)
    endpoint = endpoint_id or preset.selected_endpoint_id
    record = get_record(provider, endpoint, model) if model else None
    verification = record.result if record is not None else Verification.UNKNOWN
    return ModelCapability(
        provider_id=provider,
        model_id=model,
        endpoint_id=endpoint,
        structured_output=CapabilitySupport.UNKNOWN,
        reasoning=CapabilitySupport.UNKNOWN,
        verification=verification,
        structured_output_strategy=(
            record.schema_strategy
            if record is not None
            else preset.strategy_for_model(model)
            if model
            else StructuredOutputStrategy.NONE
        ),
        verified_at=record.verified_at
        if record is not None and record.result == Verification.VERIFIED
        else None,
    )
