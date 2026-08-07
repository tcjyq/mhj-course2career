import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
APPROVED_DEEPSEEK_MODELS = frozenset({"deepseek-v4-flash", "deepseek-v4-pro"})
MODEL_ID_PATTERN = re.compile(r"^deepseek-[a-z0-9][a-z0-9-]{0,63}$")


class ModelDiscoveryError(RuntimeError):
    """DeepSeek模型目录不可用或不满足安全选择条件。"""


@dataclass(frozen=True)
class ModelCatalogSnapshot:
    available_models: tuple[str, ...]
    fetched_at: datetime
    stale: bool = False


@dataclass(frozen=True)
class ModelSelection:
    primary_model: str
    fallback_models: tuple[str, ...]
    source: str
    catalog: ModelCatalogSnapshot | None = None


@dataclass(frozen=True)
class _CacheEntry:
    snapshot: ModelCatalogSnapshot
    fetched_monotonic: float


ClientFactory = Callable[[str, float], Any]


class DeepSeekModelCatalog:
    """发现、缓存并安全选择DeepSeek模型，不保存或记录API Key。"""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10,
        cache_seconds: int = 1800,
        stale_seconds: int = 86400,
        client_factory: ClientFactory | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.timeout_seconds = max(float(timeout_seconds), 1.0)
        self.cache_seconds = max(int(cache_seconds), 1)
        self.stale_seconds = max(int(stale_seconds), self.cache_seconds)
        self._client_factory = client_factory or _create_deepseek_client
        self._clock = clock or time.monotonic
        self._cache: dict[str, _CacheEntry] = {}

    def get_models(
        self,
        api_key: str,
        *,
        force_refresh: bool = False,
    ) -> ModelCatalogSnapshot:
        if not api_key:
            raise ModelDiscoveryError("未配置 DeepSeek API Key，无法刷新模型列表。")
        cache_key = _key_fingerprint(api_key)
        cached = self._cache.get(cache_key)
        now = self._clock()
        if (
            cached is not None
            and not force_refresh
            and now - cached.fetched_monotonic <= self.cache_seconds
        ):
            return cached.snapshot

        try:
            snapshot = self._fetch_models(api_key)
        except Exception as exc:
            if (
                cached is not None
                and now - cached.fetched_monotonic <= self.stale_seconds
            ):
                return replace(cached.snapshot, stale=True)
            raise ModelDiscoveryError("无法获取 DeepSeek 可用模型列表。") from exc

        self._cache[cache_key] = _CacheEntry(snapshot, now)
        return snapshot

    def peek(self, api_key: str) -> ModelCatalogSnapshot | None:
        """返回当前进程缓存，不触发外部请求。"""
        if not api_key:
            return None
        cached = self._cache.get(_key_fingerprint(api_key))
        if cached is None:
            return None
        age = self._clock() - cached.fetched_monotonic
        return replace(cached.snapshot, stale=age > self.cache_seconds)

    def resolve(
        self,
        api_key: str,
        *,
        mode: str,
        configured_model: str,
        preference: tuple[str, ...],
    ) -> ModelSelection:
        if configured_model not in APPROVED_DEEPSEEK_MODELS:
            raise ModelDiscoveryError("配置的 DeepSeek 模型尚未通过兼容性验证。")
        if mode == "pinned":
            return ModelSelection(configured_model, (), "pinned")
        if mode != "auto_safe":
            raise ModelDiscoveryError("不支持的 DeepSeek 模型选择模式。")

        try:
            catalog = self.get_models(api_key)
        except ModelDiscoveryError:
            return ModelSelection(configured_model, (), "configured_fallback")

        available = set(catalog.available_models)
        candidates = tuple(
            dict.fromkeys(
                model
                for model in preference
                if model in APPROVED_DEEPSEEK_MODELS and model in available
            )
        )
        if not candidates:
            raise ModelDiscoveryError("DeepSeek 当前没有经过验证的可用模型。")
        source = "stale_catalog" if catalog.stale else "live_catalog"
        return ModelSelection(candidates[0], candidates[1:], source, catalog)

    def _fetch_models(self, api_key: str) -> ModelCatalogSnapshot:
        client = self._client_factory(api_key, self.timeout_seconds)
        response = client.models.list()
        data = getattr(response, "data", None)
        if data is None:
            raise ModelDiscoveryError("DeepSeek 模型目录响应缺少 data 字段。")

        model_ids: set[str] = set()
        for item in data:
            model_id = getattr(item, "id", None)
            owned_by = getattr(item, "owned_by", None)
            if (
                isinstance(model_id, str)
                and owned_by == "deepseek"
                and MODEL_ID_PATTERN.fullmatch(model_id)
            ):
                model_ids.add(model_id)
        if not model_ids:
            raise ModelDiscoveryError("DeepSeek 模型目录没有有效模型。")
        return ModelCatalogSnapshot(
            available_models=tuple(sorted(model_ids)),
            fetched_at=datetime.now(UTC),
        )


def _create_deepseek_client(api_key: str, timeout_seconds: float) -> Any:
    from openai import OpenAI

    return OpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
        timeout=timeout_seconds,
    )


def _key_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
