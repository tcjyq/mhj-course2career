"""模型级能力与真实验证状态；目录和外部价格留给 C08-C。"""

from dataclasses import dataclass
from enum import StrEnum

from course2career.llm_provider import ProviderName
from course2career.model_catalog import APPROVED_DEEPSEEK_MODELS
from course2career.provider_registry import get_provider_preset
from course2career.provider_verification import Verification, get_record
from course2career.structured_output import StructuredOutputStrategy


class CapabilitySupport(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelCapability:
    provider_id: ProviderName
    model_id: str
    structured_output: CapabilitySupport
    reasoning: CapabilitySupport
    verification: Verification
    structured_output_strategy: StructuredOutputStrategy


def model_capability(
    provider: ProviderName, model: str, endpoint_id: str | None = None
) -> ModelCapability:
    preset = get_provider_preset(provider)
    selected_endpoint = endpoint_id or preset.selected_endpoint_id
    if not model:
        return ModelCapability(
            provider,
            model,
            CapabilitySupport.UNKNOWN,
            CapabilitySupport.UNKNOWN,
            Verification.UNKNOWN,
            StructuredOutputStrategy.NONE,
        )
    record = get_record(provider, selected_endpoint, model)
    verification = record.result if record is not None else Verification.UNKNOWN
    if provider == ProviderName.DEEPSEEK:
        if model in APPROVED_DEEPSEEK_MODELS:
            return ModelCapability(
                provider,
                model,
                CapabilitySupport.SUPPORTED,
                CapabilitySupport.UNSUPPORTED,
                verification,
                StructuredOutputStrategy.JSON_OBJECT,
            )
        return ModelCapability(
            provider,
            model,
            CapabilitySupport.UNKNOWN,
            CapabilitySupport.UNKNOWN,
            Verification.UNSUPPORTED,
            StructuredOutputStrategy.NONE,
        )
    return ModelCapability(
        provider,
        model,
        CapabilitySupport.SUPPORTED
        if verification in {Verification.SCHEMA_COMPATIBLE, Verification.VERIFIED}
        else CapabilitySupport.UNSUPPORTED
        if verification == Verification.UNSUPPORTED
        else CapabilitySupport.UNKNOWN,
        CapabilitySupport.UNKNOWN,
        verification,
        record.schema_strategy
        if record is not None
        else preset.strategy_for_model(model),
    )
