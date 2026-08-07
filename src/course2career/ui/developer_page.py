import pandas as pd
import streamlit as st

from course2career.api_key_service import APIKeyService
from course2career.llm_provider import ProviderName
from course2career.permissions import (
    PermissionDeniedError,
    Plan,
    Principal,
)

PROVIDER_LABELS = {
    ProviderName.OPENAI: "OpenAI",
    ProviderName.DEEPSEEK: "DeepSeek",
}


def render_developer_page(
    principal: Principal,
    api_key_service: APIKeyService | None,
    configuration_error: str | None,
) -> None:
    st.title("开发者API Key")
    st.caption("按供应商管理自己的Key。完整密钥不会在保存后再次显示。")

    if principal.plan not in {Plan.DEVELOPER, Plan.ADMIN}:
        st.info("此功能属于Developer方案。可在会员页面查看方案差异。")
        return
    if api_key_service is None:
        st.warning(
            configuration_error
            or "平台未配置API Key加密主密钥，暂时不能安全保存开发者Key。"
        )
        return

    def submit_api_key() -> None:
        provider = st.session_state.get(
            "developer_api_key_provider", ProviderName.OPENAI
        )
        api_key = st.session_state.get("developer_api_key_input", "")
        try:
            api_key_service.save_key(principal, provider, api_key)
            st.session_state.developer_key_feedback = "API Key已加密保存。"
        except (PermissionDeniedError, ValueError) as exc:
            st.session_state.developer_key_error = str(exc)
        finally:
            st.session_state.developer_api_key_input = ""

    feedback = st.session_state.pop("developer_key_feedback", None)
    if feedback:
        st.success(feedback)
    error = st.session_state.pop("developer_key_error", None)
    if error:
        st.error(error)

    saved_keys = api_key_service.list_keys(principal)
    st.markdown("## 已保存的Key")
    if saved_keys:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "供应商": PROVIDER_LABELS[key.provider],
                        "末四位": key.last_four,
                        "更新时间": key.updated_time,
                    }
                    for key in saved_keys
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        delete_provider = st.selectbox(
            "删除指定供应商Key",
            [key.provider for key in saved_keys],
            format_func=lambda provider: PROVIDER_LABELS[provider],
        )
        if st.button("删除Key"):
            api_key_service.delete_key(principal, delete_provider)
            st.session_state.developer_key_feedback = "API Key已删除。"
            st.rerun()
    else:
        st.info("尚未保存API Key。")

    st.markdown("## 保存或更新")
    with st.form("developer_api_key_form"):
        st.selectbox(
            "供应商",
            list(ProviderName),
            format_func=lambda item: PROVIDER_LABELS[item],
            key="developer_api_key_provider",
        )
        st.text_input(
            "API Key",
            type="password",
            autocomplete="off",
            help="保存后使用环境主密钥加密，数据库不存储明文。",
            key="developer_api_key_input",
        )
        st.form_submit_button(
            "加密保存",
            type="primary",
            on_click=submit_api_key,
        )

    with st.expander("安全说明"):
        st.write("Key使用AES-256-GCM加密，并绑定当前用户与供应商。")
        st.write("平台页面、日志和报告只显示末四位，不显示完整Key。")
