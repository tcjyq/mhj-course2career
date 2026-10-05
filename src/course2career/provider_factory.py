from dataclasses import replace

from course2career.api_key_service import APIKeyService
from course2career.config import SYSTEM_AI_HARD_MAX_OUTPUT_TOKENS, Settings
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
from course2career.provider_access import (
    AccessMode,
    CredentialResolutionError,
    CredentialResolver,
)
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
        self.credential_resolver = CredentialResolver(settings, api_key_service)
        self.model_catalog = model_catalog or DeepSeekModelCatalog(
            timeout_seconds=settings.openai_timeout_seconds,
            cache_seconds=getattr(settings, "deepseek_model_cache_seconds", 1800),
            stale_seconds=getattr(settings, "deepseek_model_stale_seconds", 86400),
        )

    def validate_system_selection(
        self,
        principal: Principal,
        provider: ProviderName,
        model: str,
        endpoint_id: str | None = None,
    ) -> None:
        """Reject unsupported system selections without touching a Provider network."""
        try:
            preset = get_provider_preset(provider, self.settings)
            preset.endpoint(endpoint_id or preset.selected_endpoint_id)
        except ValueError as exc:
            raise ProviderError(str(exc)) from exc
        if (
            not model
            or len(model) > 128
            or preset.system_key_setting is None
            or model != preset.configured_model(self.settings)
        ):
            raise ProviderError("系统模型选择无效。")
        if principal.plan == Plan.FREE and provider != ProviderName.DEEPSEEK:
            raise ProviderError("免费套餐的系统AI仅使用 DeepSeek。")
        if not self.settings.system_ai_enabled:
            raise ProviderError("系统AI当前已暂停，请使用本地规则模式。")
        if not getattr(self.settings, preset.system_key_setting):
            raise ProviderError("平台模型暂时不可用。")

    def create(
        self,
        principal: Principal,
        *,
        provider: ProviderName,
        key_mode: str,
        model: str,
        endpoint_id: str | None = None,
        access_mode: AccessMode = AccessMode.API,
    ) -> LLMProvider:
        try:
            preset = get_provider_preset(provider, self.settings)
            preset.access(access_mode)
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
        api_key = self._resolve_api_key(
            principal, provider, key_mode, access_mode=access_mode
        )
        if provider == ProviderName.OPENAI:
            provider_settings = replace(
                self.settings,
                openai_api_key=api_key,
                openai_model=model,
            )
            return OpenAIJDClient(
                provider_settings,
                max_retries=0,
                max_output_tokens=(
                    min(
                        1500,
                        SYSTEM_AI_HARD_MAX_OUTPUT_TOKENS,
                        self.settings.system_ai_max_output_tokens,
                    )
                    if key_mode == "system"
                    else 1500
                ),
            )
        if provider == ProviderName.DEEPSEEK:
            try:
                selection = self.model_catalog.resolve(
                    api_key,
                    mode=getattr(self.settings, "deepseek_model_mode", "pinned"),
                    configured_model=model,
                    preference=getattr(
                        self.settings,
                        "deepseek_model_preference",
                        ("deepseek-flash", "deepseek-v4-pro"),
                    ),
                    refresh_if_needed=True,
                )
            except ModelDiscoveryError as exc:
                raise ProviderError(str(exc)) from exc
            return DeepSeekProvider(
                api_key=api_key,
                max_retries=0,
                saved_model=model,
                model=selection.primary_model,
                fallback_models=selection.fallback_models,
                max_output_tokens=(
                    min(
                        self.settings.deepseek_max_output_tokens,
                        SYSTEM_AI_HARD_MAX_OUTPUT_TOKENS,
                        self.settings.system_ai_max_output_tokens,
                    )
                    if key_mode == "system"
                    else self.settings.deepseek_max_output_tokens
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
        *,
        access_mode: AccessMode = AccessMode.API,
    ) -> str:
        preset = get_provider_preset(provider, self.settings)
        try:
            return self.credential_resolver.resolve(
                principal, preset, key_mode, access_mode=access_mode
            ).require_usable()
        except CredentialResolutionError as exc:
            raise ProviderError(str(exc)) from exc
