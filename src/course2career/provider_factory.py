from dataclasses import replace

from course2career.api_key_service import APIKeyNotFoundError, APIKeyService
from course2career.config import Settings
from course2career.key_encryption import KeyDecryptionError
from course2career.llm_client import OpenAIJDClient
from course2career.llm_provider import LLMProvider, ProviderName
from course2career.llm_providers import DeepSeekProvider, ProviderError
from course2career.permissions import Principal


class LLMProviderFactory:
    """根据供应商和密钥模式创建统一的LLMProvider。"""

    def __init__(
        self,
        settings: Settings,
        api_key_service: APIKeyService | None = None,
    ) -> None:
        self.settings = settings
        self.api_key_service = api_key_service

    def create(
        self,
        principal: Principal,
        *,
        provider: ProviderName,
        key_mode: str,
        model: str,
    ) -> LLMProvider:
        api_key = self._resolve_api_key(principal, provider, key_mode)
        if provider == ProviderName.OPENAI:
            provider_settings = replace(
                self.settings,
                openai_api_key=api_key,
                openai_model=model,
            )
            return OpenAIJDClient(provider_settings)
        if provider == ProviderName.DEEPSEEK:
            return DeepSeekProvider(
                api_key=api_key,
                model=model,
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

        api_key = (
            self.settings.openai_api_key
            if provider == ProviderName.OPENAI
            else self.settings.deepseek_api_key
        )
        if not api_key:
            provider_label = "OpenAI" if provider == ProviderName.OPENAI else "DeepSeek"
            raise ProviderError(f"未配置平台 {provider_label} API Key。")
        return api_key
