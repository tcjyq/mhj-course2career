"""静态官方 Provider 预设；用户输入永远不能决定请求端点。"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType

from course2career.config import Settings
from course2career.llm_provider import ProviderName
from course2career.model_catalog import DEEPSEEK_BASE_URL


class ProviderProtocol(StrEnum):
    OPENAI_RESPONSES = "openai_responses"
    OPENAI_CHAT = "openai_chat"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    GEMINI_NATIVE = "gemini_native"


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
    primary_protocol: ProviderProtocol
    official_endpoint_by_region: Mapping[str, str]
    selected_endpoint_id: str
    api_key_help_url: str
    auth_scheme: str
    default_model: str | None
    model_discovery_strategy: str
    structured_output_strategy: str
    reasoning_strategy: str
    usage_strategy: str
    capability_adapter_id: str | None
    pricing_source_policy: str
    status: str
    system_key_setting: str | None = None
    cost_setting_prefix: str | None = None
    model_setting: str | None = None

    @property
    def allowed_endpoint_ids(self) -> tuple[str, ...]:
        return tuple(self.official_endpoint_by_region)

    @property
    def base_url(self) -> str:
        return self.endpoint(self.selected_endpoint_id)

    @property
    def protocol(self) -> ProviderProtocol:
        return self.primary_protocol

    @property
    def supports_byok(self) -> bool:
        return True

    @property
    def supports_model_discovery(self) -> bool:
        return self.model_discovery_strategy == "auto_safe"

    @property
    def supports_structured_output(self) -> bool:
        return self.structured_output_strategy == "json_object"

    def endpoint(self, endpoint_id: str) -> str:
        try:
            return self.official_endpoint_by_region[endpoint_id]
        except KeyError as exc:
            raise ValueError("不支持的官方端点。") from exc

    def configured_model(self, settings: Settings) -> str | None:
        return (
            getattr(settings, self.model_setting)
            if self.model_setting is not None
            else self.default_model
        )

    def cost_rates(self, settings: Settings) -> tuple[float | None, float | None]:
        if self.cost_setting_prefix is None:
            return None, None
        return (
            getattr(settings, f"{self.cost_setting_prefix}_input_cost_per_million"),
            getattr(settings, f"{self.cost_setting_prefix}_output_cost_per_million"),
        )


def _endpoints(**regions: str) -> Mapping[str, str]:
    return MappingProxyType(
        {name.removesuffix("_"): url for name, url in regions.items()}
    )


PROVIDER_PRESETS: Mapping[ProviderName, ProviderPreset] = MappingProxyType(
    {
        ProviderName.OPENAI: ProviderPreset(
            ProviderName.OPENAI,
            "OpenAI",
            ProviderProtocol.OPENAI_RESPONSES,
            _endpoints(global_="https://api.openai.com/v1"),
            "global",
            "https://platform.openai.com/api-keys",
            "bearer",
            "gpt-5.6-luna",
            "later",
            "responses_pydantic",
            "model_specific",
            "responses_usage",
            None,
            "configured_rates",
            "legacy",
            "openai_api_key",
            "openai",
            "openai_model",
        ),
        ProviderName.DEEPSEEK: ProviderPreset(
            ProviderName.DEEPSEEK,
            "DeepSeek",
            ProviderProtocol.OPENAI_CHAT,
            _endpoints(global_=DEEPSEEK_BASE_URL),
            "global",
            "https://platform.deepseek.com/api_keys",
            "bearer",
            "deepseek-v4-flash",
            "auto_safe",
            "json_object",
            "disabled_by_default",
            "chat_usage",
            "deepseek_auto_safe",
            "configured_rates",
            "legacy",
            "deepseek_api_key",
            "deepseek",
            "deepseek_model",
        ),
        ProviderName.BAILIAN: ProviderPreset(
            ProviderName.BAILIAN,
            "阿里云百炼",
            ProviderProtocol.OPENAI_CHAT,
            BAILIAN_BASE_URLS,
            "cn-beijing",
            "https://help.aliyun.com/en/model-studio/get-api-key",
            "bearer",
            "qwen-plus",
            "later",
            "prompt_json",
            "model_specific",
            "chat_usage",
            None,
            "configured_rates",
            "candidate",
            cost_setting_prefix="bailian",
        ),
        ProviderName.OPENROUTER: ProviderPreset(
            ProviderName.OPENROUTER,
            "OpenRouter",
            ProviderProtocol.OPENAI_CHAT,
            _endpoints(global_="https://openrouter.ai/api/v1"),
            "global",
            "https://openrouter.ai/settings/keys",
            "bearer",
            None,
            "later",
            "prompt_json",
            "model_specific",
            "chat_usage",
            None,
            "configured_rates",
            "candidate",
            cost_setting_prefix="openrouter",
        ),
        ProviderName.SILICONFLOW: ProviderPreset(
            ProviderName.SILICONFLOW,
            "SiliconFlow",
            ProviderProtocol.OPENAI_CHAT,
            _endpoints(cn="https://api.siliconflow.cn/v1"),
            "cn",
            "https://docs.siliconflow.cn/docs/userguide/quickstart",
            "bearer",
            None,
            "later",
            "prompt_json",
            "model_specific",
            "chat_usage",
            None,
            "unknown",
            "candidate",
        ),
        ProviderName.MOONSHOT: ProviderPreset(
            ProviderName.MOONSHOT,
            "Moonshot / Kimi",
            ProviderProtocol.OPENAI_CHAT,
            _endpoints(cn="https://api.moonshot.cn/v1"),
            "cn",
            "https://platform.kimi.com/docs/api/chat",
            "bearer",
            None,
            "later",
            "prompt_json",
            "model_specific",
            "chat_usage",
            None,
            "unknown",
            "candidate",
        ),
        ProviderName.ZHIPU: ProviderPreset(
            ProviderName.ZHIPU,
            "Zhipu / GLM",
            ProviderProtocol.OPENAI_CHAT,
            _endpoints(cn="https://open.bigmodel.cn/api/paas/v4"),
            "cn",
            "https://docs.bigmodel.cn/cn/guide/develop/http/introduction",
            "bearer",
            None,
            "later",
            "prompt_json",
            "model_specific",
            "chat_usage",
            None,
            "unknown",
            "candidate",
        ),
        ProviderName.MINIMAX: ProviderPreset(
            ProviderName.MINIMAX,
            "MiniMax",
            ProviderProtocol.OPENAI_CHAT,
            _endpoints(global_="https://api.minimax.io/v1"),
            "global",
            "https://platform.minimax.io/docs/api-reference/text-openai-api",
            "bearer",
            "MiniMax-M3",
            "later",
            "prompt_json",
            "model_specific",
            "chat_usage",
            "minimax_text_only",
            "unknown",
            "candidate",
        ),
        ProviderName.GEMINI: ProviderPreset(
            ProviderName.GEMINI,
            "Google Gemini",
            ProviderProtocol.GEMINI_NATIVE,
            _endpoints(global_="https://generativelanguage.googleapis.com/v1beta"),
            "global",
            "https://ai.google.dev/gemini-api/docs/api-key",
            "x-goog-api-key",
            None,
            "later",
            "json_mime",
            "model_specific",
            "gemini_usage",
            None,
            "unknown",
            "candidate",
        ),
        ProviderName.ANTHROPIC: ProviderPreset(
            ProviderName.ANTHROPIC,
            "Anthropic Claude",
            ProviderProtocol.ANTHROPIC_MESSAGES,
            _endpoints(global_="https://api.anthropic.com"),
            "global",
            "https://console.anthropic.com/settings/keys",
            "x-api-key",
            None,
            "later",
            "prompt_json",
            "model_specific",
            "messages_usage",
            None,
            "unknown",
            "candidate",
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
        if settings.bailian_base_url:
            endpoint_ids = [
                name
                for name, url in BAILIAN_BASE_URLS.items()
                if url == settings.bailian_base_url
            ]
            if not endpoint_ids:
                raise ValueError("百炼 Base URL 必须是受控区域端点。")
            return replace(preset, selected_endpoint_id=endpoint_ids[0])
        if settings.bailian_region not in BAILIAN_BASE_URLS:
            raise ValueError("不支持的百炼服务区域。")
        return replace(preset, selected_endpoint_id=settings.bailian_region)
    return preset


def ui_provider_presets() -> tuple[ProviderPreset, ...]:
    """所有 Developer/Admin 可配置的官方预设；能否分析另看 Key 与模型。"""
    return tuple(PROVIDER_PRESETS.values())
