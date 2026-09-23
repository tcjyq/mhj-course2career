"""由官方注册表生成的 Developer BYOK 配置页。"""

from collections.abc import Callable

import streamlit as st

from course2career.api_key_service import APIKeyMetadata, APIKeyService
from course2career.llm_provider import ProviderName
from course2career.model_capability import Verification, model_capability
from course2career.permissions import (
    Permission,
    PermissionDeniedError,
    Principal,
    authorize,
)
from course2career.product_repository import StoredProviderProfile
from course2career.provider_connection import test_provider_connection
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_profile import ProviderProfileService
from course2career.provider_registry import ProviderPreset, ui_provider_presets


def render_developer_page(
    principal: Principal,
    api_key_service: APIKeyService | None,
    configuration_error: str | None,
    profile_service: ProviderProfileService | None = None,
    provider_factory: LLMProviderFactory | None = None,
) -> None:
    st.title("我的 AI Provider")
    st.caption("使用自己的 API Key；保存后只显示末四位。新增预设尚需真实模型验证。")
    try:
        authorize(principal, Permission.CONFIGURE_OWN_API_KEY)
    except PermissionDeniedError:
        st.info("此功能仅对 Developer / Admin 开放。")
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
    ) -> None:
        endpoint_id = st.session_state[endpoint_key]
        model_id = st.session_state[model_key]
        new_key = st.session_state.get(secret_key, "")
        feedback_key = f"provider_feedback_{provider.value}"
        try:
            profile_service.validate_selection(provider, endpoint_id, model_id)
            if not new_key and provider not in keys:
                raise ValueError("请先填写该供应商的 API Key。")
            if new_key:
                api_key_service.save_key(principal, provider, new_key)
            profile_service.save(principal, provider, endpoint_id, model_id)
            st.session_state[feedback_key] = "配置已保存；模型仍须真实验证。"
        except (PermissionDeniedError, ValueError) as exc:
            st.session_state[feedback_key] = str(exc)
        finally:
            st.session_state.pop(secret_key, None)
            st.session_state[f"provider_form_version_{provider.value}"] = version + 1

    for preset in presets:
        _render_provider_card(
            preset,
            principal,
            keys.get(preset.provider_id),
            profiles.get(preset.provider_id),
            api_key_service,
            profile_service,
            provider_factory,
            save_provider,
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
    save_provider: Callable[[ProviderName, str, str, str, int], None],
) -> None:
    provider = preset.provider_id
    name = provider.value
    selected_endpoint = (
        profile.endpoint_id if profile is not None else preset.selected_endpoint_id
    )
    selected_model = (
        profile.model_id if profile is not None else preset.default_model or ""
    )
    version = int(st.session_state.get(f"provider_form_version_{name}", 0))
    endpoint_key = f"provider_endpoint_{name}_{version}"
    model_key = f"provider_model_{name}_{version}"
    secret_key = f"provider_secret_{name}_{version}"
    with st.container(border=True):
        st.markdown(f"### {preset.display_name}")
        st.caption(f"协议：{preset.primary_protocol.value} · 官方端点")
        st.write("状态：已配置" if key_metadata is not None else "状态：未配置")
        if key_metadata is not None:
            st.write(f"API Key：••••{key_metadata.last_four}")
        capability = model_capability(provider, selected_model, selected_endpoint)
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
        last_connection = st.session_state.get(f"provider_connection_{name}")
        if (
            key_metadata is not None
            and last_connection is not None
            and last_connection[:2] == (selected_endpoint, selected_model)
        ):
            st.caption(last_connection[2])
        if preset.pricing_source_policy == "unknown":
            st.caption("费用估算未配置")
        st.link_button("获取官方 API Key / 文档", preset.api_key_help_url)
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
            st.text_input("模型 ID", value=selected_model, key=model_key)
            st.text_input(
                "API Key（更新时填写新 Key）",
                type="password",
                autocomplete="off",
                key=secret_key,
            )
            st.form_submit_button(
                "保存配置",
                on_click=save_provider,
                args=(provider, endpoint_key, model_key, secret_key, version),
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
