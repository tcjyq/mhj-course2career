"""B1 的最小模型级能力状态；动态目录与外部价格留给 C08-C。"""

from dataclasses import dataclass
from enum import StrEnum

from course2career.llm_provider import ProviderName
from course2career.model_catalog import APPROVED_DEEPSEEK_MODELS


class Verification(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


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


def model_capability(provider: ProviderName, model: str) -> ModelCapability:
    if not model:
        return ModelCapability(
            provider,
            model,
            CapabilitySupport.UNKNOWN,
            CapabilitySupport.UNKNOWN,
            Verification.UNKNOWN,
        )
    if provider == ProviderName.DEEPSEEK:
        if model in APPROVED_DEEPSEEK_MODELS:
            return ModelCapability(
                provider,
                model,
                CapabilitySupport.SUPPORTED,
                CapabilitySupport.UNSUPPORTED,
                Verification.VERIFIED,
            )
        return ModelCapability(
            provider,
            model,
            CapabilitySupport.UNKNOWN,
            CapabilitySupport.UNKNOWN,
            Verification.UNSUPPORTED,
        )
    return ModelCapability(
        provider,
        model,
        CapabilitySupport.UNKNOWN,
        CapabilitySupport.UNKNOWN,
        Verification.UNVERIFIED,
    )
