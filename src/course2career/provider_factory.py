from dataclasses import replace

from course2career.api_key_service import APIKeyNotFoundError, APIKeyService
from course2career.config import Settings
from course2career.key_encryption import KeyDecryptionError
from course2career.llm_client import OpenAIJDClient
from course2career.llm_provider import LLMProvider, ProviderName
from course2career.llm_providers import (
    DeepSeekProvider,
    OpenAICompatibleChatProvider,
    ProviderError,
)
from course2career.model_catalog import (
    DeepSeekModelCatalog,
    ModelDiscoveryError,
)
from course2career.native_providers import AnthropicMessagesProvider, GeminiProvider
from course2career.permissions import Plan, Principal
from course2career.provider_registry import ProviderProtocol, get_provider_preset
from course2career.provider_verification import Verification, get_record


class LLMProviderFactory:
    """根据供应商和密钥模式创建统一的LLMProvider。"""

    def __init__(
        self,
        settings: Settings,
        api_key_service: APIKeyService | None = None,
        model_catalog: DeepSeekModelCatalog | None = None,
    ) -> None:
        self.settings = settings
        self.api_key_service = api_key_service
        self.model_catalog = model_catalog or DeepSeekModelCatalog(
            timeout_seconds=settings.openai_timeout_seconds,
            cache_seconds=getattr(settings, "deepseek_model_cache_seconds", 1800),
            stale_seconds=getattr(settings, "deepseek_model_stale_seconds", 86400),
        )

    def create(
        self,
        principal: Principal,
        *,
        provider: ProviderName,
        key_mode: str,
        model: str,
        endpoint_id: str | None = None,
    ) -> LLMProvider:
        try:
            preset = get_provider_preset(provider, self.settings)
        except ValueError as exc:
            raise ProviderError(str(exc)) from exc
        provider = preset.provider_id
        try:
            preset.endpoint(endpoint_id or preset.selected_endpoint_id)
        except ValueError as exc:
            raise ProviderError(str(exc)) from exc
        if (
            key_mode == "system"
            and principal.plan == Plan.FREE
            and provider != ProviderName.DEEPSEEK
        ):
            raise ProviderError("免费套餐的系统AI仅使用 DeepSeek。")
        api_key = self._resolve_api_key(principal, provider, key_mode)
        if provider == ProviderName.OPENAI:
            provider_settings = replace(
                self.settings,
                openai_api_key=api_key,
                openai_model=model,
            )
            return OpenAIJDClient(provider_settings)
        if provider == ProviderName.DEEPSEEK:
            try:
                selection = self.model_catalog.resolve(
                    api_key,
                    mode=getattr(self.settings, "deepseek_model_mode", "pinned"),
                    configured_model=model,
                    preference=getattr(
                        self.settings,
                        "deepseek_model_preference",
                        ("deepseek-v4-flash", "deepseek-v4-pro"),
                    ),
                )
            except ModelDiscoveryError as exc:
                raise ProviderError(str(exc)) from exc
            return DeepSeekProvider(
                api_key=api_key,
                model=selection.primary_model,
                fallback_models=selection.fallback_models,
                max_output_tokens=getattr(
                    self.settings, "deepseek_max_output_tokens", 1500
                ),
                timeout_seconds=self.settings.openai_timeout_seconds,
            )
        if (
            key_mode == "user"
            and preset.primary_protocol == ProviderProtocol.OPENAI_CHAT
        ):
            verification = get_record(
                provider,
                endpoint_id or preset.selected_endpoint_id,
                model or preset.default_model or "",
            )
            return OpenAICompatibleChatProvider(
                preset=preset,
                api_key=api_key,
                model=model or preset.default_model or "",
                endpoint_id=endpoint_id,
                timeout_seconds=self.settings.openai_timeout_seconds,
                structured_strategy=(
                    verification.schema_strategy
                    if provider == ProviderName.OPENROUTER
                    and verification is not None
                    and verification.result == Verification.VERIFIED
                    else None
                ),
            )
        if (
            key_mode == "user"
            and preset.primary_protocol == ProviderProtocol.ANTHROPIC_MESSAGES
        ):
            return AnthropicMessagesProvider(
                preset=preset,
                api_key=api_key,
                model=model or preset.default_model or "",
                endpoint_id=endpoint_id,
                timeout_seconds=self.settings.openai_timeout_seconds,
            )
        if (
            key_mode == "user"
            and preset.primary_protocol == ProviderProtocol.GEMINI_NATIVE
        ):
            return GeminiProvider(
                preset=preset,
                api_key=api_key,
                model=model or preset.default_model or "",
                endpoint_id=endpoint_id,
                timeout_seconds=self.settings.openai_timeout_seconds,
            )
        raise ProviderError("不支持的模型供应商。")

    def _resolve_api_key(
        self,
        principal: Principal,
        provider: ProviderName,
        key_mode: str,
    ) -> str:
        if key_mode == "user":
            if self.api_key_service is None:
                raise ProviderError("开发者API Key服务未配置。")
            try:
                return self.api_key_service.get_key(principal, provider)
            except (APIKeyNotFoundError, KeyDecryptionError) as exc:
                raise ProviderError(
                    "无法读取开发者API Key，请重新保存后再试。"
                ) from exc
        if key_mode != "system":
            raise ProviderError("不支持的API Key模式。")
        if not getattr(self.settings, "system_ai_enabled", True):
            raise ProviderError("系统AI当前已暂停，请使用本地规则模式。")

        preset = get_provider_preset(provider, self.settings)
        if preset.system_key_setting is None:
            raise ProviderError("该供应商未开放系统API Key模式。")
        api_key = getattr(self.settings, preset.system_key_setting)
        if not api_key:
            raise ProviderError(f"未配置平台 {preset.display_name} API Key。")
        return api_key
