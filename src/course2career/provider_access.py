"""Access semantics are separate from credential ownership and quota ownership."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from course2career.api_key_service import APIKeyNotFoundError, APIKeyService
from course2career.config import Settings
from course2career.key_encryption import KeyDecryptionError
from course2career.llm_provider import ProviderName
from course2career.permissions import Principal

if TYPE_CHECKING:
    from course2career.provider_registry import ProviderPreset


class AccessMode(StrEnum):
    API = "api"
    PLAN = "plan"
    OAUTH_SUBSCRIPTION = "oauth_subscription"


class CredentialKind(StrEnum):
    API_KEY = "api_key"
    PLAN_KEY = "plan_key"
    OAUTH = "oauth"


class CredentialResolutionError(RuntimeError):
    """Fixed messages only; credentials never appear in diagnostics."""


@dataclass(frozen=True)
class ResolvedCredential:
    provider: ProviderName
    access_mode: AccessMode
    kind: CredentialKind
    owner: str
    secret: str = field(repr=False)
    expires_at: datetime | None = None

    def require_usable(self) -> str:
        if not self.secret or (
            self.expires_at is not None
            and (self.expires_at.tzinfo is None or self.expires_at <= datetime.now(UTC))
        ):
            raise CredentialResolutionError("凭证无效或已过期，请重新配置。")
        return self.secret


class CredentialResolver:
    """No ambient fallback: BYOK failure never consumes a System AI credential.

    Resolve on sensitive operations only. Never cache/serialize ResolvedCredential.
    APIKeyService remains the encrypted, current-user API_KEY implementation.
    """

    def __init__(
        self, settings: Settings, api_key_service: APIKeyService | None = None
    ) -> None:
        self.settings = settings
        self.api_key_service = api_key_service

    def resolve(
        self,
        principal: Principal,
        preset: "ProviderPreset",
        owner: str,
        access_mode: AccessMode = AccessMode.API,
    ) -> ResolvedCredential:
        access = preset.access(access_mode)
        if owner == "user":
            if self.api_key_service is None:
                raise CredentialResolutionError("开发者API Key服务未配置。")
            try:
                secret = self.api_key_service.get_key(principal, preset.provider_id)
            except (APIKeyNotFoundError, KeyDecryptionError) as exc:
                raise CredentialResolutionError(
                    "无法读取开发者API Key，请重新保存后再试。"
                ) from exc
        elif owner == "system":
            if not self.settings.system_ai_enabled:
                raise CredentialResolutionError(
                    "系统AI当前已暂停，请使用本地规则模式。"
                )
            if preset.system_key_setting is None:
                raise CredentialResolutionError("该供应商未开放系统API Key模式。")
            secret = getattr(self.settings, preset.system_key_setting)
            if not secret:
                raise CredentialResolutionError(
                    f"未配置平台 {preset.display_name} API Key。"
                )
        else:
            raise CredentialResolutionError("不支持的API Key模式。")
        credential = ResolvedCredential(
            preset.provider_id, access.mode, access.credential_kind, owner, secret
        )
        credential.require_usable()
        return credential
