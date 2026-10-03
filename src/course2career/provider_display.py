"""One-render, non-secret Provider data. Never used to authorize an action."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType

from course2career.api_key_service import APIKeyMetadata, APIKeyService
from course2career.llm_provider import ProviderName
from course2career.permissions import PermissionDeniedError, Principal
from course2career.product_repository import StoredProviderProfile
from course2career.provider_profile import ProviderProfileService


@dataclass(frozen=True)
class ProviderDisplayView:
    principal: Principal
    keys: Mapping[ProviderName, APIKeyMetadata]
    profiles: Mapping[ProviderName, StoredProviderProfile]
    _active: bool = True

    def require_owner(self, principal: Principal) -> None:
        if not self._active or principal != self.principal:
            raise PermissionDeniedError("账户展示数据已失效，请重新加载页面。")


@contextmanager
def provider_display_view(
    principal: Principal,
    api_keys: APIKeyService | None,
    profiles: ProviderProfileService | None,
) -> Iterator[ProviderDisplayView | None]:
    view = None
    if api_keys is not None:
        try:
            # list_keys rechecks the persistent BYOK switch. No Secret is decrypted.
            keys = api_keys.list_keys(principal)
        except PermissionDeniedError:
            pass
        else:
            stored_profiles = (
                profiles.repository.list_provider_profiles(principal.user_id)
                if profiles is not None
                else []
            )
            view = ProviderDisplayView(
                principal,
                MappingProxyType({key.provider: key for key in keys}),
                MappingProxyType(
                    {ProviderName(p.provider): p for p in stored_profiles}
                ),
            )
    try:
        yield view
    finally:
        if view is not None:
            object.__setattr__(view, "_active", False)
