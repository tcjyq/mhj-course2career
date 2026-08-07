from types import SimpleNamespace

import pytest

from course2career.model_catalog import (
    APPROVED_DEEPSEEK_MODELS,
    DeepSeekModelCatalog,
    ModelDiscoveryError,
)


class FakeModelsAPI:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.call_count = 0

    def list(self) -> object:
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        if isinstance(response, Exception):
            raise response
        return response


def _catalog(models_api: FakeModelsAPI, *, clock=None) -> DeepSeekModelCatalog:
    client = SimpleNamespace(models=models_api)
    return DeepSeekModelCatalog(
        timeout_seconds=5,
        cache_seconds=30,
        stale_seconds=300,
        client_factory=lambda _api_key, _timeout: client,
        clock=clock,
    )


def test_catalog_validates_and_filters_external_model_data() -> None:
    models_api = FakeModelsAPI(
        [
            SimpleNamespace(
                data=[
                    SimpleNamespace(id="deepseek-v4-pro", owned_by="deepseek"),
                    SimpleNamespace(id="deepseek-v4-flash", owned_by="deepseek"),
                    SimpleNamespace(id="deepseek-evil/../../", owned_by="deepseek"),
                    SimpleNamespace(id="deepseek-v4-flash", owned_by="other"),
                ]
            )
        ]
    )

    snapshot = _catalog(models_api).get_models("secret-key")

    assert snapshot.available_models == (
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    )
    assert snapshot.stale is False


def test_catalog_uses_cache_and_force_refresh_bypasses_it() -> None:
    models_api = FakeModelsAPI(
        [
            SimpleNamespace(
                data=[SimpleNamespace(id="deepseek-v4-flash", owned_by="deepseek")]
            ),
            SimpleNamespace(
                data=[SimpleNamespace(id="deepseek-v4-pro", owned_by="deepseek")]
            ),
        ]
    )
    catalog = _catalog(models_api)

    first = catalog.get_models("secret-key")
    cached = catalog.get_models("secret-key")
    refreshed = catalog.get_models("secret-key", force_refresh=True)

    assert first.available_models == cached.available_models
    assert refreshed.available_models == ("deepseek-v4-pro",)
    assert models_api.call_count == 2


def test_expired_catalog_falls_back_to_stale_cache_on_discovery_failure() -> None:
    now = [0.0]
    models_api = FakeModelsAPI(
        [
            SimpleNamespace(
                data=[SimpleNamespace(id="deepseek-v4-flash", owned_by="deepseek")]
            ),
            RuntimeError("provider unavailable"),
        ]
    )
    catalog = _catalog(models_api, clock=lambda: now[0])
    catalog.get_models("secret-key")
    now[0] = 31

    snapshot = catalog.get_models("secret-key")

    assert snapshot.available_models == ("deepseek-v4-flash",)
    assert snapshot.stale is True


def test_pinned_mode_never_calls_model_discovery() -> None:
    models_api = FakeModelsAPI([RuntimeError("must not be called")])
    catalog = _catalog(models_api)

    selection = catalog.resolve(
        "secret-key",
        mode="pinned",
        configured_model="deepseek-v4-flash",
        preference=("deepseek-v4-flash", "deepseek-v4-pro"),
    )

    assert selection.primary_model == "deepseek-v4-flash"
    assert selection.fallback_models == ()
    assert selection.source == "pinned"
    assert models_api.call_count == 0


def test_auto_safe_selects_only_available_approved_models_in_preference_order() -> None:
    models_api = FakeModelsAPI(
        [
            SimpleNamespace(
                data=[
                    SimpleNamespace(id="deepseek-v5-preview", owned_by="deepseek"),
                    SimpleNamespace(id="deepseek-v4-pro", owned_by="deepseek"),
                    SimpleNamespace(id="deepseek-v4-flash", owned_by="deepseek"),
                ]
            )
        ]
    )

    selection = _catalog(models_api).resolve(
        "secret-key",
        mode="auto_safe",
        configured_model="deepseek-v4-flash",
        preference=("deepseek-v4-pro", "deepseek-v4-flash", "deepseek-v5-preview"),
    )

    assert selection.primary_model == "deepseek-v4-pro"
    assert selection.fallback_models == ("deepseek-v4-flash",)
    assert selection.source == "live_catalog"
    assert "deepseek-v5-preview" not in APPROVED_DEEPSEEK_MODELS


def test_auto_safe_uses_configured_model_when_catalog_is_unreachable() -> None:
    models_api = FakeModelsAPI([RuntimeError("provider unavailable")])

    selection = _catalog(models_api).resolve(
        "secret-key",
        mode="auto_safe",
        configured_model="deepseek-v4-flash",
        preference=("deepseek-v4-flash", "deepseek-v4-pro"),
    )

    assert selection.primary_model == "deepseek-v4-flash"
    assert selection.fallback_models == ()
    assert selection.source == "configured_fallback"


def test_auto_safe_rejects_catalog_without_approved_models() -> None:
    models_api = FakeModelsAPI(
        [
            SimpleNamespace(
                data=[SimpleNamespace(id="deepseek-v5-preview", owned_by="deepseek")]
            )
        ]
    )

    with pytest.raises(ModelDiscoveryError, match="没有经过验证的可用模型"):
        _catalog(models_api).resolve(
            "secret-key",
            mode="auto_safe",
            configured_model="deepseek-v4-flash",
            preference=("deepseek-v4-flash", "deepseek-v4-pro"),
        )
