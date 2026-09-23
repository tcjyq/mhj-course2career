"""受控 Provider 预设；新增供应商不能从请求中注入任意端点。"""

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Literal

from course2career.config import Settings
from course2career.llm_provider import ProviderName
from course2career.model_catalog import DEEPSEEK_BASE_URL

ProviderProtocol = Literal["responses", "openai_compatible_chat"]

BAILIAN_BASE_URLS = MappingProxyType(
    {
        "cn-beijing": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "ap-southeast-1": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "us-east-1": "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
        "cn-hongkong": "https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1",
    }
)


@dataclass(frozen=True)
class ProviderPreset:
    provider_id: ProviderName
    display_name: str
    protocol: ProviderProtocol
    base_url: str | None
    default_model: str | None
    supports_byok: bool
    supports_model_discovery: bool
    supports_structured_output: bool
    supports_thinking: bool
    model_catalog_strategy: str
    system_key_setting: str | None = None
    cost_setting_prefix: str = ""
    available_in_ui: bool = False
    model_setting: str | None = None

    def configured_model(self, settings: Settings) -> str | None:
        return (
            getattr(settings, self.model_setting)
            if self.model_setting is not None
            else self.default_model
        )

    def cost_rates(self, settings: Settings) -> tuple[float, float]:
        return (
            getattr(settings, f"{self.cost_setting_prefix}_input_cost_per_million"),
            getattr(settings, f"{self.cost_setting_prefix}_output_cost_per_million"),
        )


PROVIDER_PRESETS = MappingProxyType(
    {
        ProviderName.OPENAI: ProviderPreset(
            ProviderName.OPENAI,
            "OpenAI",
            "responses",
            None,
            "gpt-5.6-luna",
            True,
            False,
            True,
            False,
            "configured",
            "openai_api_key",
            "openai",
            True,
            "openai_model",
        ),
        ProviderName.DEEPSEEK: ProviderPreset(
            ProviderName.DEEPSEEK,
            "DeepSeek",
            "openai_compatible_chat",
            DEEPSEEK_BASE_URL,
            "deepseek-v4-flash",
            True,
            True,
            True,
            True,
            "deepseek_auto_safe",
            "deepseek_api_key",
            "deepseek",
            True,
            "deepseek_model",
        ),
        ProviderName.BAILIAN: ProviderPreset(
            ProviderName.BAILIAN,
            "阿里云百炼",
            "openai_compatible_chat",
            BAILIAN_BASE_URLS["cn-beijing"],
            "qwen-plus",
            True,
            False,
            False,
            False,
            "configured",
            cost_setting_prefix="bailian",
        ),
        ProviderName.OPENROUTER: ProviderPreset(
            ProviderName.OPENROUTER,
            "OpenRouter",
            "openai_compatible_chat",
            "https://openrouter.ai/api/v1",
            None,
            True,
            False,
            False,
            False,
            "explicit_model_pending_discovery",
            cost_setting_prefix="openrouter",
        ),
    }
)


def get_provider_preset(
    provider: ProviderName | str, settings: Settings | None = None
) -> ProviderPreset:
    try:
        provider_id = ProviderName(provider)
        preset = PROVIDER_PRESETS[provider_id]
    except (ValueError, KeyError) as exc:
        raise ValueError("不支持的模型供应商。") from exc
    if provider_id == ProviderName.BAILIAN and settings is not None:
        try:
            base_url = (
                settings.bailian_base_url or BAILIAN_BASE_URLS[settings.bailian_region]
            )
        except KeyError as exc:
            raise ValueError("不支持的百炼服务区域。") from exc
        if base_url not in BAILIAN_BASE_URLS.values():
            raise ValueError("百炼 Base URL 必须是受控区域端点。")
        return replace(preset, base_url=base_url)
    return preset


def ui_provider_presets() -> tuple[ProviderPreset, ...]:
    """C08-A 仅保留已发布的两种页面选择，后续阶段再启用新预设。"""
    return tuple(
        preset for preset in PROVIDER_PRESETS.values() if preset.available_in_ui
    )
