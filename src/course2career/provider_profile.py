"""用户对官方 Provider 的最小偏好；API Key 仅由 APIKeyService 保存。"""

import re
from datetime import UTC, datetime

from course2career.byok_mode import require_current_byok_access
from course2career.llm_provider import ProviderName
from course2career.model_catalog import APPROVED_DEEPSEEK_MODELS
from course2career.permissions import Principal
from course2career.product_repository import (
    SQLiteProductRepository,
    StoredProviderProfile,
)
from course2career.provider_registry import get_provider_preset

MODEL_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,199}\Z")


class ProviderProfileService:
    def __init__(self, repository: SQLiteProductRepository) -> None:
        self.repository = repository

    def validate_selection(
        self, provider: ProviderName, endpoint_id: str, model_id: str
    ) -> str:
        preset = get_provider_preset(provider)
        preset.endpoint(endpoint_id)
        cleaned_model = model_id.strip()
        if not MODEL_ID_PATTERN.fullmatch(cleaned_model):
            raise ValueError("模型 ID 格式无效。")
        if provider == ProviderName.DEEPSEEK and cleaned_model not in (
            APPROVED_DEEPSEEK_MODELS
        ):
            raise ValueError("DeepSeek 模型尚未通过 Auto-Safe 白名单。")
        return cleaned_model

    def save(
        self,
        principal: Principal,
        provider: ProviderName,
        endpoint_id: str,
        model_id: str,
    ) -> StoredProviderProfile:
        require_current_byok_access(principal, self.repository)
        if principal.user_id is None:
            raise PermissionError("登录后才能管理 Provider。")
        cleaned_model = self.validate_selection(provider, endpoint_id, model_id)
        existing = self.repository.get_provider_profile(
            principal.user_id, provider.value
        )
        now = datetime.now(UTC).isoformat()
        profile = StoredProviderProfile(
            user_id=principal.user_id,
            provider=provider.value,
            endpoint_id=endpoint_id,
            model_id=cleaned_model,
            created_time=existing.created_time if existing is not None else now,
            updated_time=now,
        )
        self.repository.upsert_provider_profile(profile)
        return profile

    def get(
        self, principal: Principal, provider: ProviderName
    ) -> StoredProviderProfile | None:
        require_current_byok_access(principal, self.repository)
        if principal.user_id is None:
            raise PermissionError("登录后才能使用 Provider。")
        return self.repository.get_provider_profile(principal.user_id, provider.value)

    def list(self, principal: Principal) -> list[StoredProviderProfile]:
        require_current_byok_access(principal, self.repository)
        if principal.user_id is None:
            raise PermissionError("登录后才能管理 Provider。")
        return self.repository.list_provider_profiles(principal.user_id)

    def delete(self, principal: Principal, provider: ProviderName) -> None:
        require_current_byok_access(principal, self.repository)
        if principal.user_id is None:
            raise PermissionError("登录后才能管理 Provider。")
        self.repository.delete_provider_profile(principal.user_id, provider.value)
