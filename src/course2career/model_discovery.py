"""受控官方模型目录；只缓存无密钥元数据，B2 验证仍独立。"""

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from course2career.api_key_service import APIKeyNotFoundError, APIKeyService
from course2career.byok_mode import require_current_byok_access
from course2career.key_encryption import KeyDecryptionError
from course2career.llm_provider import ProviderName
from course2career.model_capability import (
    CapabilitySupport,
    LifecycleStatus,
    ModelCapability,
    PricingMetadata,
    model_capability,
)
from course2career.permissions import Principal
from course2career.provider_profile import MODEL_ID_PATTERN, WORKSPACE_ID_PATTERN
from course2career.provider_registry import (
    DiscoveryStrategy,
    ProviderPreset,
    get_provider_preset,
)

HttpGetter = Callable[[str, Mapping[str, str], Mapping[str, str]], Mapping[str, Any]]
DEEPSEEK_PRICING = "https://api-docs.deepseek.com/quick_start/pricing/"
DEEPSEEK_CATALOG = "https://api-docs.deepseek.com/api/list-models/"
BAILIAN_CATALOG = "https://help.aliyun.com/en/model-studio/list-models"
SILICONFLOW_CATALOG = "https://api-docs.siliconflow.cn/docs/api/models-get"
KIMI_CATALOG = "https://platform.kimi.com/docs/models"
ZHIPU_CATALOG = "https://docs.bigmodel.cn/cn/guide/models/text/glm-5.1"
MINIMAX_CATALOG = (
    "https://platform.minimax.io/docs/api-reference/models/openai/list-models"
)
OPENROUTER_CATALOG = (
    "https://openrouter.ai/docs/api/api-reference/models/"
    "list-all-models-and-their-properties"
)
OPENAI_CATALOG = "https://platform.openai.com/docs/api-reference/models/list"
ANTHROPIC_CATALOG = "https://platform.claude.com/docs/en/api/models/list"
GEMINI_CATALOG = "https://ai.google.dev/api/models"
CHECKED_AT = "2026-09-24"


class CatalogError(RuntimeError):
    """仅向 UI 暴露不含凭证或供应商原文的目录错误。"""


@dataclass(frozen=True)
class CatalogSnapshot:
    provider_id: ProviderName
    endpoint_id: str
    models: tuple[ModelCapability, ...]
    last_success_at: str
    stale: bool = False
    warning: str | None = None


class ModelDiscoveryAdapter(Protocol):
    def discover_models(
        self,
        principal: Principal,
        provider: ProviderName,
        endpoint_id: str,
        *,
        workspace_id: str | None = None,
        force_refresh: bool = False,
    ) -> CatalogSnapshot: ...


def _official_get(
    url: str, headers: Mapping[str, str], params: Mapping[str, str]
) -> Mapping[str, Any]:
    with httpx.Client(timeout=8.0, follow_redirects=False) as client:
        response = client.get(url, headers=dict(headers), params=dict(params))
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise CatalogError("官方模型目录响应过大。")
        payload = response.json()
    if not isinstance(payload, dict):
        raise CatalogError("官方模型目录格式无效。")
    return payload


def _string(value: Any, limit: int = 200) -> str | None:
    return (
        value[:limit]
        if isinstance(value, str) and value and value.isprintable()
        else None
    )


def _positive_int(value: Any) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _price(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if 0 <= number < 1_000_000_000 and number == number else None


def _support(value: Any) -> CapabilitySupport:
    if value is True:
        return CapabilitySupport.SUPPORTED
    if value is False:
        return CapabilitySupport.UNSUPPORTED
    return CapabilitySupport.UNKNOWN


def _model(
    provider: ProviderName,
    endpoint: str,
    model_id: Any,
    *,
    name: Any = None,
    text: CapabilitySupport = CapabilitySupport.UNKNOWN,
    structured: CapabilitySupport = CapabilitySupport.UNKNOWN,
    reasoning: CapabilitySupport = CapabilitySupport.UNKNOWN,
    context: Any = None,
    max_output: Any = None,
    pricing: PricingMetadata | None = None,
    source_url: str,
    capability_source: str | None = None,
    lifecycle: LifecycleStatus = LifecycleStatus.CURRENT,
    replacement: str | None = None,
    checked_at: str,
) -> ModelCapability | None:
    if not isinstance(model_id, str) or not MODEL_ID_PATTERN.fullmatch(model_id):
        return None
    base = model_capability(provider, model_id, endpoint)
    return replace(
        base,
        display_name=_string(name) or model_id,
        text_generation=text,
        structured_output=structured,
        reasoning=reasoning,
        context_window=_positive_int(context),
        max_output_tokens=_positive_int(max_output),
        pricing=pricing or PricingMetadata(),
        availability_source=source_url,
        capability_source=capability_source,
        source_url=source_url,
        discovered_at=checked_at,
        checked_at=checked_at,
        lifecycle_status=lifecycle,
        replacement_model=replacement,
    )


def _deepseek_metadata(
    endpoint: str, model_id: Any, checked_at: str
) -> ModelCapability | None:
    if not isinstance(model_id, str) or model_id not in {
        "deepseek-flash",
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    }:
        return None
    alias = model_id == "deepseek-v4-flash"
    pro = model_id == "deepseek-v4-pro"
    item = _model(
        ProviderName.DEEPSEEK,
        endpoint,
        model_id,
        text=CapabilitySupport.SUPPORTED,
        structured=CapabilitySupport.SUPPORTED,
        reasoning=CapabilitySupport.SUPPORTED,
        context=1_000_000,
        max_output=384_000,
        pricing=PricingMetadata(
            input_price=4.5 if pro else 1.0,
            output_price=13.5 if pro else 4.0,
            cached_input_price=0.15 if pro else 0.02,
            currency="CNY",
            unit="per 1M tokens",
            source=DEEPSEEK_PRICING,
            checked_at=CHECKED_AT,
            note="非高峰基础价；工作日高峰价更高，调用前请核对官方页面。",
        ),
        source_url=DEEPSEEK_PRICING,
        capability_source=DEEPSEEK_PRICING,
        lifecycle=LifecycleStatus.COMPATIBILITY_ALIAS
        if alias
        else LifecycleStatus.CURRENT,
        replacement="deepseek-flash" if alias else None,
        checked_at=checked_at,
    )
    return (
        replace(
            item,
            availability_source=DEEPSEEK_PRICING if alias else DEEPSEEK_CATALOG,
        )
        if item is not None
        else None
    )


def _static_catalog(
    provider: ProviderName, endpoint: str, checked_at: str
) -> tuple[ModelCapability, ...]:
    if provider == ProviderName.MOONSHOT:
        specs = (
            ("kimi-k2.6", 256_000, 6.5, 27.0, 1.1),
            ("kimi-k2.7-code", 256_000, 6.5, 27.0, 1.3),
            ("kimi-k3", 1_000_000, 20.0, 100.0, 2.0),
        )
        return tuple(
            item
            for model_id, context, input_price, output_price, cached_price in specs
            if (
                item := _model(
                    provider,
                    endpoint,
                    model_id,
                    text=CapabilitySupport.SUPPORTED,
                    structured=CapabilitySupport.UNKNOWN,
                    reasoning=CapabilitySupport.SUPPORTED,
                    context=context,
                    pricing=PricingMetadata(
                        input_price,
                        output_price,
                        cached_price,
                        "CNY",
                        "per 1M tokens",
                        "https://platform.kimi.com/",
                        checked_at,
                        "官网基础价；缓存写入与其他计费条件另计。",
                    ),
                    source_url=KIMI_CATALOG,
                    capability_source=KIMI_CATALOG,
                    checked_at=CHECKED_AT,
                )
            )
        )
    if provider == ProviderName.ZHIPU:
        item = _model(
            provider,
            endpoint,
            "glm-5.1",
            text=CapabilitySupport.SUPPORTED,
            structured=CapabilitySupport.SUPPORTED,
            reasoning=CapabilitySupport.SUPPORTED,
            context=200_000,
            max_output=128_000,
            pricing=PricingMetadata(
                currency="CNY",
                unit="per 1M tokens",
                source="https://open.bigmodel.cn/pricing",
                checked_at=CHECKED_AT,
                note="官方价格页需登录/脚本查看，数值未核实。",
            ),
            source_url=ZHIPU_CATALOG,
            capability_source=ZHIPU_CATALOG,
            checked_at=checked_at,
        )
        return (item,) if item else ()
    return ()


class ModelCatalogService:
    """用户、端点、业务空间和 Key 版本隔离的内存目录缓存。"""

    def __init__(
        self,
        api_keys: APIKeyService,
        *,
        getter: HttpGetter = _official_get,
        ttl_seconds: int = 1800,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.api_keys = api_keys
        self.getter = getter
        self.ttl_seconds = max(ttl_seconds, 1)
        self.clock = clock
        self.now = now
        self._cache: dict[
            tuple[str, str, str, str, str], tuple[CatalogSnapshot, float]
        ] = {}

    def _cache_key(
        self,
        principal: Principal,
        preset: ProviderPreset,
        endpoint_id: str,
        workspace_id: str | None,
    ) -> tuple[str, str, str, str, str] | None:
        if principal.user_id is None:
            return None
        version = "static"
        if preset.model_discovery_strategy != DiscoveryStrategy.STATIC_OFFICIAL_CATALOG:
            stored = self.api_keys.repository.get_api_key(
                principal.user_id, preset.provider_id.value
            )
            if stored is None:
                return None
            version = stored.updated_time
        return (
            principal.user_id,
            preset.provider_id.value,
            endpoint_id,
            workspace_id or "",
            version,
        )

    def peek(
        self,
        principal: Principal,
        provider: ProviderName,
        endpoint_id: str,
        *,
        workspace_id: str | None = None,
    ) -> CatalogSnapshot | None:
        require_current_byok_access(principal, self.api_keys.repository)
        preset = get_provider_preset(provider)
        preset.endpoint(endpoint_id)
        key = self._cache_key(principal, preset, endpoint_id, workspace_id)
        entry = self._cache.get(key) if key is not None else None
        if entry is None:
            return None
        snapshot, fetched = entry
        return replace(
            snapshot,
            stale=snapshot.stale or self.clock() - fetched > self.ttl_seconds,
        )

    def discover_models(
        self,
        principal: Principal,
        provider: ProviderName,
        endpoint_id: str,
        *,
        workspace_id: str | None = None,
        force_refresh: bool = False,
    ) -> CatalogSnapshot:
        require_current_byok_access(principal, self.api_keys.repository)
        preset = get_provider_preset(provider)
        preset.endpoint(endpoint_id)
        if workspace_id and not WORKSPACE_ID_PATTERN.fullmatch(workspace_id):
            raise CatalogError("业务空间 ID 格式无效。")
        key = self._cache_key(principal, preset, endpoint_id, workspace_id)
        entry = self._cache.get(key) if key is not None else None
        if entry and not force_refresh and self.clock() - entry[1] <= self.ttl_seconds:
            return entry[0]
        checked_at = self.now().isoformat(timespec="seconds")
        try:
            if (
                preset.model_discovery_strategy
                == DiscoveryStrategy.STATIC_OFFICIAL_CATALOG
            ):
                models = _static_catalog(provider, endpoint_id, CHECKED_AT)
            else:
                api_key = self.api_keys.get_key(principal, provider)
                rows = self._fetch_rows(preset, endpoint_id, workspace_id, api_key)
                models = self._map_rows(provider, endpoint_id, rows, checked_at)
            if not models:
                raise CatalogError("官方目录没有可用于文本生成的模型。")
        except (
            APIKeyNotFoundError,
            KeyDecryptionError,
            CatalogError,
            httpx.HTTPError,
            ValueError,
            TypeError,
        ) as exc:
            if entry is not None:
                stale = replace(
                    entry[0],
                    stale=True,
                    warning="刷新未成功，显示最近一次成功的目录。",
                )
                self._cache[key] = (stale, entry[1])
                return stale
            if isinstance(exc, APIKeyNotFoundError):
                raise CatalogError("请先保存该供应商的 API Key。") from None
            if isinstance(exc, KeyDecryptionError):
                raise CatalogError(
                    "已保存的 API Key 无法解密，请检查加密配置。"
                ) from None
            if isinstance(exc, CatalogError):
                raise
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {
                401,
                403,
            }:
                raise CatalogError("目录鉴权失败，请检查对应区域的 API Key。") from None
            raise CatalogError("官方模型目录暂时不可用或格式无效。") from None
        snapshot = CatalogSnapshot(provider, endpoint_id, models, checked_at)
        if key is not None:
            if len(self._cache) >= 1024:
                oldest = min(self._cache, key=lambda item: self._cache[item][1])
                del self._cache[oldest]
            self._cache[key] = (snapshot, self.clock())
        return snapshot

    def _request(
        self, url: str, headers: Mapping[str, str], params: Mapping[str, str]
    ) -> Mapping[str, Any]:
        payload = self.getter(url, headers, params)
        if not isinstance(payload, Mapping):
            raise CatalogError("官方模型目录格式无效。")
        return payload

    def _fetch_rows(
        self,
        preset: ProviderPreset,
        endpoint_id: str,
        workspace_id: str | None,
        api_key: str,
    ) -> list[Mapping[str, Any]]:
        strategy = preset.model_discovery_strategy
        headers = {"Authorization": f"Bearer {api_key}"}
        if strategy == DiscoveryStrategy.BAILIAN_MODELS:
            if endpoint_id in {"cn-beijing", "us-east-1"}:
                if not workspace_id:
                    raise CatalogError("该区域查询目录需要业务空间 ID。")
                region_host = (
                    "cn-beijing" if endpoint_id == "cn-beijing" else "us-east-1"
                )
                url = (
                    f"https://{workspace_id}.{region_host}.maas.aliyuncs.com"
                    "/api/v1/models"
                )
            elif endpoint_id == "ap-southeast-1":
                url = "https://dashscope-intl.aliyuncs.com/api/v1/models"
            else:
                url = "https://cn-hongkong.dashscope.aliyuncs.com/api/v1/models"
            rows: list[Mapping[str, Any]] = []
            for page in range(1, 21):
                payload = self._request(
                    url,
                    headers,
                    {"page_no": str(page), "page_size": "100", "capabilities": "TG"},
                )
                output = payload.get("output")
                if not isinstance(output, Mapping) or not isinstance(
                    output.get("models"), list
                ):
                    raise CatalogError("百炼模型目录格式无效。")
                rows.extend(
                    item for item in output["models"] if isinstance(item, Mapping)
                )
                total = _positive_int(output.get("total"))
                if total is None or len(rows) >= total:
                    return rows
            raise CatalogError("百炼模型目录分页超过上限。")

        url = preset.base_url.rstrip("/") + "/models"
        if strategy == DiscoveryStrategy.DEEPSEEK_MODELS:
            url = "https://api.deepseek.com/models"
        elif strategy == DiscoveryStrategy.ANTHROPIC_MODELS:
            url = "https://api.anthropic.com/v1/models"
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        elif strategy == DiscoveryStrategy.GEMINI_MODELS:
            url = "https://generativelanguage.googleapis.com/v1beta/models"
            headers = {"x-goog-api-key": api_key}
        elif strategy == DiscoveryStrategy.SILICONFLOW_MODELS:
            url = "https://api.siliconflow.cn/v1/models"
        elif strategy == DiscoveryStrategy.MINIMAX_MODELS:
            url = preset.endpoint(endpoint_id).rstrip("/") + "/models"
        elif strategy == DiscoveryStrategy.OPENROUTER_MODELS:
            url = "https://openrouter.ai/api/v1/models"
        elif strategy != DiscoveryStrategy.OPENAI_MODELS:
            raise CatalogError("该供应商尚无受控模型目录。")

        if strategy == DiscoveryStrategy.GEMINI_MODELS:
            rows = []
            page_token = ""
            for _ in range(20):
                params = {"pageSize": "100"}
                if page_token:
                    params["pageToken"] = page_token
                payload = self._request(url, headers, params)
                page_rows = payload.get("models")
                if not isinstance(page_rows, list):
                    raise CatalogError("Gemini 模型目录格式无效。")
                rows.extend(item for item in page_rows if isinstance(item, Mapping))
                page_token = payload.get("nextPageToken") or ""
                if not page_token:
                    return rows
            raise CatalogError("Gemini 模型目录分页超过上限。")
        if strategy == DiscoveryStrategy.ANTHROPIC_MODELS:
            rows = []
            cursor = ""
            for _ in range(20):
                params = {"limit": "100"}
                if cursor:
                    params["after_id"] = cursor
                payload = self._request(url, headers, params)
                page_rows = payload.get("data")
                if not isinstance(page_rows, list):
                    raise CatalogError("Anthropic 模型目录格式无效。")
                rows.extend(item for item in page_rows if isinstance(item, Mapping))
                if not payload.get("has_more"):
                    return rows
                cursor = payload.get("last_id") or ""
                if not cursor:
                    raise CatalogError("Anthropic 模型目录分页游标无效。")
            raise CatalogError("Anthropic 模型目录分页超过上限。")
        if strategy == DiscoveryStrategy.OPENROUTER_MODELS:
            rows = []
            for offset in range(0, 5000, 500):
                payload = self._request(
                    url, headers, {"limit": "500", "offset": str(offset)}
                )
                page_rows = payload.get("data")
                if not isinstance(page_rows, list):
                    raise CatalogError("OpenRouter 模型目录格式无效。")
                rows.extend(item for item in page_rows if isinstance(item, Mapping))
                if len(page_rows) < 500:
                    return rows
            raise CatalogError("OpenRouter 模型目录分页超过上限。")
        params = (
            {"sub_type": "chat"}
            if strategy == DiscoveryStrategy.SILICONFLOW_MODELS
            else {}
        )
        payload = self._request(url, headers, params)
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise CatalogError("官方模型目录格式无效。")
        return [item for item in rows if isinstance(item, Mapping)]

    def _map_rows(
        self,
        provider: ProviderName,
        endpoint_id: str,
        rows: list[Mapping[str, Any]],
        checked_at: str,
    ) -> tuple[ModelCapability, ...]:
        result: dict[str, ModelCapability] = {}
        for row in rows:
            item = self._map_row(provider, endpoint_id, row, checked_at)
            if item is not None:
                result[item.model_id] = item
        if provider == ProviderName.DEEPSEEK and "deepseek-flash" in result:
            alias = _deepseek_metadata(endpoint_id, "deepseek-v4-flash", checked_at)
            if alias is not None:
                result[alias.model_id] = alias
        return tuple(result.values())

    def _map_row(
        self,
        provider: ProviderName,
        endpoint_id: str,
        row: Mapping[str, Any],
        checked_at: str,
    ) -> ModelCapability | None:
        if provider == ProviderName.DEEPSEEK:
            if row.get("owned_by") != "deepseek":
                return None
            return _deepseek_metadata(endpoint_id, row.get("id"), checked_at) or _model(
                provider,
                endpoint_id,
                row.get("id"),
                source_url=DEEPSEEK_CATALOG,
                checked_at=checked_at,
            )
        if provider == ProviderName.BAILIAN:
            model_id = row.get("model")
            features = row.get("features")
            capabilities = row.get("capabilities")
            feature_set = (
                set(features)
                if isinstance(features, list)
                and all(isinstance(item, str) for item in features)
                else set()
            )
            capability_set = (
                set(capabilities)
                if isinstance(capabilities, list)
                and all(isinstance(item, str) for item in capabilities)
                else set()
            )
            info = row.get("model_info")
            info = info if isinstance(info, Mapping) else {}
            prices = row.get("prices")
            base_price: Mapping[str, Any] | None = None
            if isinstance(prices, list):
                base_price = next(
                    (
                        item
                        for item in prices
                        if isinstance(item, Mapping)
                        and item.get("range_name") == "Default"
                    ),
                    None,
                )
            price_items = base_price.get("prices") if base_price else None
            price_map = (
                {
                    item.get("type"): item
                    for item in price_items
                    if isinstance(item, Mapping) and isinstance(item.get("type"), str)
                }
                if isinstance(price_items, list)
                else {}
            )
            input_entry = price_map.get("input_token", {})
            output_entry = price_map.get("output_token", {})
            unit = input_entry.get("price_unit") or output_entry.get("price_unit")
            known_unit = "per 1M tokens" if unit == "per million tokens" else None
            pricing = PricingMetadata(
                input_price=_price(input_entry.get("price")) if known_unit else None,
                output_price=_price(output_entry.get("price")) if known_unit else None,
                currency="CNY" if known_unit else None,
                unit=known_unit,
                source=BAILIAN_CATALOG if known_unit else None,
                checked_at=checked_at if known_unit else None,
                note="仅默认区间；其他上下文长度、地域或时段可能另有价格。"
                if known_unit
                else None,
            )
            offline = row.get("inference_offline_info")
            offline_time = (
                offline.get("offline_time") if isinstance(offline, Mapping) else None
            )
            lifecycle = LifecycleStatus.CURRENT
            if isinstance(offline_time, str) and offline_time:
                try:
                    offline_date = datetime.fromisoformat(
                        offline_time.replace("Z", "+00:00")
                    )
                    lifecycle = (
                        LifecycleStatus.RETIRED
                        if offline_date.date() < datetime.now(UTC).date()
                        else LifecycleStatus.DEPRECATED
                    )
                except ValueError:
                    lifecycle = LifecycleStatus.DEPRECATED
            return _model(
                provider,
                endpoint_id,
                model_id,
                name=row.get("name"),
                text=CapabilitySupport.SUPPORTED,
                structured=CapabilitySupport.SUPPORTED
                if "structured-outputs" in feature_set
                else CapabilitySupport.UNKNOWN,
                reasoning=CapabilitySupport.SUPPORTED
                if "Reasoning" in capability_set
                else CapabilitySupport.UNKNOWN,
                context=info.get("context_window"),
                max_output=info.get("max_output_tokens"),
                pricing=pricing,
                source_url=BAILIAN_CATALOG,
                capability_source=BAILIAN_CATALOG,
                lifecycle=lifecycle,
                checked_at=checked_at,
            )
        if provider == ProviderName.OPENROUTER:
            model_id = row.get("id")
            if isinstance(model_id, str) and model_id in {"openrouter/auto", "auto"}:
                return None
            architecture = row.get("architecture")
            architecture = architecture if isinstance(architecture, Mapping) else {}
            outputs = architecture.get("output_modalities")
            params = row.get("supported_parameters")
            param_set = (
                set(params)
                if isinstance(params, list)
                and all(isinstance(item, str) for item in params)
                else set()
            )
            prices = row.get("pricing")
            prices = prices if isinstance(prices, Mapping) else {}
            top = row.get("top_provider")
            top = top if isinstance(top, Mapping) else {}
            return _model(
                provider,
                endpoint_id,
                model_id,
                name=row.get("name"),
                text=CapabilitySupport.SUPPORTED
                if isinstance(outputs, list) and "text" in outputs
                else CapabilitySupport.UNKNOWN,
                structured=CapabilitySupport.SUPPORTED
                if "response_format" in param_set or "structured_outputs" in param_set
                else CapabilitySupport.UNKNOWN,
                context=row.get("context_length"),
                max_output=top.get("max_completion_tokens"),
                pricing=PricingMetadata(
                    input_price=_scaled_token_price(prices.get("prompt")),
                    output_price=_scaled_token_price(prices.get("completion")),
                    cached_input_price=_scaled_token_price(
                        prices.get("input_cache_read")
                    ),
                    currency="USD",
                    unit="per 1M tokens",
                    source=OPENROUTER_CATALOG,
                    checked_at=checked_at,
                    note="目录标价按 token 换算；实际路由/请求条件可能影响计费。",
                ),
                source_url=OPENROUTER_CATALOG,
                capability_source=OPENROUTER_CATALOG,
                lifecycle=LifecycleStatus.DEPRECATED
                if row.get("expiration_date")
                else LifecycleStatus.CURRENT,
                checked_at=checked_at,
            )
        if provider == ProviderName.GEMINI:
            raw_name = row.get("name")
            model_id = (
                raw_name.removeprefix("models/") if isinstance(raw_name, str) else None
            )
            methods = row.get("supportedGenerationMethods")
            if not isinstance(methods, list) or "generateContent" not in methods:
                return None
            return _model(
                provider,
                endpoint_id,
                model_id,
                name=row.get("displayName"),
                text=CapabilitySupport.SUPPORTED,
                reasoning=_support(row.get("thinking")),
                context=row.get("inputTokenLimit"),
                max_output=row.get("outputTokenLimit"),
                source_url=GEMINI_CATALOG,
                capability_source=GEMINI_CATALOG,
                checked_at=checked_at,
            )
        if provider == ProviderName.ANTHROPIC:
            caps = row.get("capabilities")
            caps = caps if isinstance(caps, Mapping) else {}
            structured = caps.get("structured_outputs")
            thinking = caps.get("thinking")
            return _model(
                provider,
                endpoint_id,
                row.get("id"),
                name=row.get("display_name"),
                text=CapabilitySupport.SUPPORTED,
                structured=_support(structured.get("supported"))
                if isinstance(structured, Mapping)
                else CapabilitySupport.UNKNOWN,
                reasoning=_support(thinking.get("supported"))
                if isinstance(thinking, Mapping)
                else CapabilitySupport.UNKNOWN,
                max_output=row.get("max_output_tokens"),
                source_url=ANTHROPIC_CATALOG,
                capability_source=ANTHROPIC_CATALOG,
                checked_at=checked_at,
            )
        source = {
            ProviderName.SILICONFLOW: SILICONFLOW_CATALOG,
            ProviderName.MINIMAX: MINIMAX_CATALOG,
            ProviderName.OPENAI: OPENAI_CATALOG,
        }[provider]
        return _model(
            provider,
            endpoint_id,
            row.get("id"),
            text=CapabilitySupport.SUPPORTED
            if provider in {ProviderName.SILICONFLOW, ProviderName.MINIMAX}
            else CapabilitySupport.UNKNOWN,
            context=1_000_000
            if provider == ProviderName.MINIMAX and row.get("id") == "MiniMax-M3"
            else None,
            source_url=source,
            capability_source=source,
            checked_at=checked_at,
        )

    def selected_model(
        self,
        principal: Principal,
        provider: ProviderName,
        endpoint_id: str,
        model_id: str,
        *,
        workspace_id: str | None = None,
    ) -> ModelCapability:
        require_current_byok_access(principal, self.api_keys.repository)
        snapshot = self.peek(
            principal, provider, endpoint_id, workspace_id=workspace_id
        )
        if snapshot is not None:
            found = next(
                (item for item in snapshot.models if item.model_id == model_id), None
            )
            if found is not None:
                return found
        if provider == ProviderName.DEEPSEEK and model_id == "deepseek-v4-flash":
            return _deepseek_metadata(
                endpoint_id, model_id, self.now().isoformat(timespec="seconds")
            ) or model_capability(provider, model_id, endpoint_id)
        if provider == ProviderName.MOONSHOT and model_id in {
            "kimi-latest",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        }:
            return replace(
                model_capability(provider, model_id, endpoint_id),
                lifecycle_status=LifecycleStatus.RETIRED,
                replacement_model="kimi-k2.6",
                source_url=KIMI_CATALOG,
            )
        return model_capability(provider, model_id, endpoint_id)


def _scaled_token_price(value: Any) -> float | None:
    price = _price(value)
    return price * 1_000_000 if price is not None else None
