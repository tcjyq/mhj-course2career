"""由官方注册表生成的 Developer BYOK 配置页。"""

from collections.abc import Callable

import streamlit as st

from course2career.api_key_service import APIKeyMetadata, APIKeyService
from course2career.byok_mode import BYOKModeService, is_legacy_byok_principal
from course2career.llm_provider import ProviderName
from course2career.model_capability import (
    CapabilitySupport,
    LifecycleStatus,
    Verification,
    model_capability,
)
from course2career.model_catalog import APPROVED_DEEPSEEK_MODELS
from course2career.model_discovery import CatalogError, ModelCatalogService
from course2career.permissions import (
    Permission,
    PermissionDeniedError,
    Principal,
    Role,
    authorize,
)
from course2career.product_repository import StoredProviderProfile
from course2career.provider_connection import test_provider_connection
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_profile import (
    WORKSPACE_ID_PATTERN,
    ProviderProfileService,
)
from course2career.provider_registry import (
    MAINLAND_PROVIDERS,
    DiscoveryStrategy,
    ProviderPreset,
    ui_provider_presets,
)
from course2career.ui.byok_mode_controls import render_byok_mode_controls


def render_developer_page(
    principal: Principal,
    api_key_service: APIKeyService | None,
    configuration_error: str | None,
    profile_service: ProviderProfileService | None = None,
    provider_factory: LLMProviderFactory | None = None,
    byok_mode_service: BYOKModeService | None = None,
    catalog_service: ModelCatalogService | None = None,
) -> None:
    active = (
        principal.role != Role.GUEST
        and principal.user_id is not None
        and (
            is_legacy_byok_principal(principal)
            or (
                byok_mode_service is not None
                and byok_mode_service.is_enabled(principal)
            )
        )
    )
    st.title("我的 AI Provider" if active else "开发者模式")
    if not active:
        st.write("连接你自己的大模型 API，模型费用由你的 API 服务商账户承担。")
        render_byok_mode_controls(principal, byok_mode_service, key_prefix="developer")
        return
    st.caption("使用自己的 API Key；保存后只显示末四位。新增预设尚需真实模型验证。")
    st.markdown("## 开发者模式")
    render_byok_mode_controls(principal, byok_mode_service, key_prefix="developer")
    try:
        authorize(principal, Permission.CONFIGURE_OWN_API_KEY)
    except PermissionDeniedError:
        st.info("请先启用开发者模式。")
        return
    if api_key_service is None:
        st.warning(
            configuration_error
            or "平台未配置 API Key 加密主密钥，暂时不能安全保存开发者 Key。"
        )
        return
    profile_service = profile_service or ProviderProfileService(
        api_key_service.repository
    )
    presets = ui_provider_presets()
    keys = {item.provider: item for item in api_key_service.list_keys(principal)}
    profiles = {
        ProviderName(item.provider): item for item in profile_service.list(principal)
    }
    configured = sum(
        preset.provider_id in keys
        and bool(
            profiles[preset.provider_id].model_id
            if preset.provider_id in profiles
            else preset.default_model
        )
        for preset in presets
    )
    verified = sum(
        model_capability(
            preset.provider_id,
            profiles[preset.provider_id].model_id
            if preset.provider_id in profiles
            else preset.default_model or "",
            profiles[preset.provider_id].endpoint_id
            if preset.provider_id in profiles
            else preset.selected_endpoint_id,
        ).verification
        == Verification.VERIFIED
        for preset in presets
        if preset.provider_id in keys
    )
    st.caption(
        f"支持预设：{len(presets)} · 已配置：{configured} · 已验证模型：{verified}"
    )

    def save_provider(
        provider: ProviderName,
        endpoint_key: str,
        model_key: str,
        secret_key: str,
        version: int,
        catalog_choice_key: str,
        workspace_key: str | None,
    ) -> None:
        endpoint_id = st.session_state[endpoint_key]
        catalog_choice = st.session_state.get(catalog_choice_key, "手动输入")
        model_id = (
            catalog_choice
            if catalog_choice != "手动输入"
            else st.session_state[model_key]
        )
        workspace_id = st.session_state.get(workspace_key) if workspace_key else None
        new_key = st.session_state.get(secret_key, "")
        feedback_key = f"provider_feedback_{provider.value}"
        try:
            profile_service.validate_selection(provider, endpoint_id, model_id)
            if workspace_id and not WORKSPACE_ID_PATTERN.fullmatch(
                workspace_id.strip()
            ):
                raise ValueError("业务空间 ID 格式无效。")
            if not new_key and provider not in keys:
                raise ValueError("请先填写该供应商的 API Key。")
            if new_key:
                api_key_service.save_key(principal, provider, new_key)
            profile_service.save(
                principal, provider, endpoint_id, model_id, workspace_id
            )
            st.session_state[feedback_key] = "配置已保存；模型仍须真实验证。"
        except (PermissionDeniedError, ValueError) as exc:
            st.session_state[feedback_key] = str(exc)
        finally:
            st.session_state.pop(secret_key, None)
            st.session_state[f"provider_form_version_{provider.value}"] = version + 1

    def render_group(group: tuple[ProviderPreset, ...]) -> None:
        for preset in group:
            _render_provider_card(
                preset,
                principal,
                keys.get(preset.provider_id),
                profiles.get(preset.provider_id),
                api_key_service,
                profile_service,
                provider_factory,
                catalog_service,
                save_provider,
            )

    st.markdown("## 大陆主流 Provider")
    render_group(tuple(p for p in presets if p.provider_id in MAINLAND_PROVIDERS))
    with st.expander("国际 / 可选 Provider"):
        render_group(
            tuple(p for p in presets if p.provider_id not in MAINLAND_PROVIDERS)
        )

    with st.expander("安全与费用说明"):
        st.write("Key 使用 AES-256-GCM 加密，并绑定当前用户与供应商。")
        st.write("BYOK 不消耗平台系统 AI 额度；费用由供应商向 Key 持有人计费。")
        st.write("未配置可靠费率时显示“费用估算未配置”，不表示免费。")


def _render_provider_card(
    preset: ProviderPreset,
    principal: Principal,
    key_metadata: APIKeyMetadata | None,
    profile: StoredProviderProfile | None,
    api_key_service: APIKeyService,
    profile_service: ProviderProfileService,
    provider_factory: LLMProviderFactory | None,
    catalog_service: ModelCatalogService | None,
    save_provider: Callable[[ProviderName, str, str, str, int, str, str | None], None],
) -> None:
    provider = preset.provider_id
    name = provider.value
    selected_endpoint = (
        profile.endpoint_id if profile is not None else preset.selected_endpoint_id
    )
    selected_model = (
        profile.model_id if profile is not None else preset.default_model or ""
    )
    workspace_id = profile.workspace_id if profile is not None else None
    snapshot = None
    if catalog_service is not None:
        try:
            if (
                preset.model_discovery_strategy
                == DiscoveryStrategy.STATIC_OFFICIAL_CATALOG
            ):
                snapshot = catalog_service.discover_models(
                    principal, provider, selected_endpoint, workspace_id=workspace_id
                )
            else:
                snapshot = catalog_service.peek(
                    principal, provider, selected_endpoint, workspace_id=workspace_id
                )
        except (CatalogError, PermissionDeniedError):
            pass
    version = int(st.session_state.get(f"provider_form_version_{name}", 0))
    endpoint_key = f"provider_endpoint_{name}_{version}"
    model_key = f"provider_model_{name}_{version}"
    secret_key = f"provider_secret_{name}_{version}"
    workspace_key = (
        f"provider_workspace_{name}_{version}"
        if provider == ProviderName.BAILIAN
        else None
    )
    catalog_choice_key = f"provider_catalog_choice_{name}_{version}"
    with st.container(border=True):
        st.markdown(f"### {preset.display_name}")
        st.caption(f"协议：{preset.primary_protocol.value} · 官方端点")
        st.write("状态：已配置" if key_metadata is not None else "状态：未配置")
        if key_metadata is not None:
            st.write(f"API Key：••••{key_metadata.last_four}")
        capability = (
            catalog_service.selected_model(
                principal,
                provider,
                selected_endpoint,
                selected_model,
                workspace_id=workspace_id,
            )
            if catalog_service is not None
            else model_capability(provider, selected_model, selected_endpoint)
        )
        labels = {
            Verification.UNKNOWN: "未验证",
            Verification.CONNECTED: "已连接",
            Verification.SCHEMA_COMPATIBLE: "Schema 兼容",
            Verification.VERIFIED: "✓ Course2Career 已验证",
            Verification.UNSUPPORTED: "当前模型不支持",
        }
        st.caption(
            f"模型：{selected_model or '待填写'} · {labels[capability.verification]}"
        )
        if capability.lifecycle_status == LifecycleStatus.COMPATIBILITY_ALIAS:
            st.warning(
                f"{selected_model} 是兼容旧名称，建议主动选择 "
                f"{capability.replacement_model} 并保存。"
            )
        elif capability.lifecycle_status == LifecycleStatus.RETIRED:
            st.warning("该模型已下线，请在目录中选择当前模型后保存。")
        if snapshot is not None:
            stale_label = "（过期缓存）" if snapshot.stale else ""
            st.caption(
                f"官方目录：{len(snapshot.models)} 个模型{stale_label} · "
                f"上次成功：{snapshot.last_success_at}"
            )
            if snapshot.warning:
                st.info(snapshot.warning)
        else:
            st.caption("官方目录：尚未刷新；模型能力与价格未知。")
        official_structured = {
            CapabilitySupport.SUPPORTED: "官方支持",
            CapabilitySupport.UNSUPPORTED: "官方不支持",
            CapabilitySupport.UNKNOWN: "未知",
        }[capability.structured_output]
        st.caption(
            f"Structured Output：{official_structured} · "
            f"Course2Career：{labels[capability.verification]}"
        )
        if capability.context_window:
            st.caption(f"上下文：{capability.context_window:,} tokens")
        if capability.input_price is not None and capability.output_price is not None:
            symbol = {"CNY": "¥", "USD": "$"}.get(capability.currency, "")
            st.caption(
                f"费用：{symbol}{capability.input_price:g} 输入 / "
                f"{symbol}{capability.output_price:g} 输出，"
                f"每百万 tokens（{capability.currency or '币种未核实'}）。"
            )
            if capability.pricing.note:
                st.caption(capability.pricing.note)
        else:
            st.caption("费用估算未配置；未知不代表免费。")
        last_connection = st.session_state.get(f"provider_connection_{name}")
        if (
            key_metadata is not None
            and last_connection is not None
            and last_connection[:2] == (selected_endpoint, selected_model)
        ):
            st.caption(last_connection[2])
        st.link_button("获取官方 API Key / 文档", preset.api_key_help_url)
        if capability.source_url:
            st.link_button("官方模型来源", capability.source_url)
        if st.button(
            "刷新模型",
            key=f"refresh_models_{name}",
            disabled=catalog_service is None
            or (
                key_metadata is None
                and preset.model_discovery_strategy
                != DiscoveryStrategy.STATIC_OFFICIAL_CATALOG
            ),
        ):
            try:
                catalog_service.discover_models(
                    principal,
                    provider,
                    selected_endpoint,
                    workspace_id=workspace_id,
                    force_refresh=True,
                )
                st.rerun()
            except CatalogError as exc:
                st.warning(str(exc))
        feedback = st.session_state.pop(f"provider_feedback_{name}", None)
        if feedback:
            st.info(feedback)
        with st.form(f"provider_form_{name}_{version}"):
            st.selectbox(
                "官方端点",
                preset.allowed_endpoint_ids,
                index=preset.allowed_endpoint_ids.index(selected_endpoint),
                key=endpoint_key,
            )
            if len(preset.allowed_endpoint_ids) > 1:
                st.caption("切换区域后先保存配置，再刷新对应区域的目录。")
            choices = ["手动输入"]
            if snapshot is not None:
                choices.extend(
                    item.model_id
                    for item in snapshot.models
                    if item.lifecycle_status != LifecycleStatus.RETIRED
                    and item.verification != Verification.UNSUPPORTED
                    and item.text_generation != CapabilitySupport.UNSUPPORTED
                    and (
                        provider != ProviderName.DEEPSEEK
                        or item.model_id in APPROVED_DEEPSEEK_MODELS
                    )
                )
            if len(choices) > 1:
                st.selectbox(
                    "目录模型（可选）",
                    choices,
                    index=choices.index(selected_model)
                    if selected_model in choices
                    else 0,
                    key=catalog_choice_key,
                )
            st.text_input("模型 ID", value=selected_model, key=model_key)
            if workspace_key is not None:
                st.text_input(
                    "百炼业务空间 ID（北京/美国目录需要）",
                    value=workspace_id or "",
                    key=workspace_key,
                )
                st.caption("修改业务空间 ID 后先保存配置，再刷新目录。")
            st.text_input(
                "API Key（更新时填写新 Key）",
                type="password",
                autocomplete="off",
                key=secret_key,
            )
            st.form_submit_button(
                "保存配置",
                on_click=save_provider,
                args=(
                    provider,
                    endpoint_key,
                    model_key,
                    secret_key,
                    version,
                    catalog_choice_key,
                    workspace_key,
                ),
            )
        if st.button(
            "测试连接（使用个人 Key，可能产生费用）",
            key=f"test_provider_{name}",
            disabled=key_metadata is None
            or not selected_model
            or provider_factory is None,
        ):
            result = test_provider_connection(
                provider_factory,
                principal,
                provider,
                selected_model,
                selected_endpoint,
            )
            connection_label = (
                "API 可连接 · Course2Career Schema 兼容"
                if result.schema_ok
                else "API 可连接 · Schema 未通过"
                if result.request_ok
                else "连接未通过"
            )
            st.session_state[f"provider_connection_{name}"] = (
                selected_endpoint,
                selected_model,
                connection_label,
            )
            if result.schema_ok:
                st.success(
                    f"{connection_label}：模型 {result.model}，"
                    f"耗时 {result.latency_ms} ms。"
                    "完整固定验证集通过后才标为 Course2Career 已验证。"
                )
            else:
                st.error(result.sanitized_error or "连接测试未通过。")
        if st.button(
            "删除配置",
            key=f"delete_provider_{name}",
            disabled=key_metadata is None and profile is None,
        ):
            api_key_service.delete_key(principal, provider)
            profile_service.delete(principal, provider)
            st.rerun()
