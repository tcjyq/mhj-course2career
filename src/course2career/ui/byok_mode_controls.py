"""账户页和 Provider Hub 共用的开发者模式开关。"""

import streamlit as st

from course2career.byok_mode import BYOKModeService, is_legacy_byok_principal
from course2career.permissions import Principal, Role


def render_byok_mode_controls(
    principal: Principal,
    service: BYOKModeService | None,
    *,
    key_prefix: str,
) -> bool:
    st.write("使用你自己的大模型 API Key，不会消耗平台 AI 调用额度。")
    st.caption(
        "API Key 由你提供并加密保存；模型费用由对应服务商向你的账户收取，"
        "平台不会代为充值。关闭开发者模式不会删除已保存的 Key。"
    )
    if principal.role == Role.GUEST or principal.user_id is None:
        st.info("请先登录，再启用开发者模式。")
        return False
    if is_legacy_byok_principal(principal):
        st.caption("当前账户保留历史开发者或管理员 BYOK 权限。")
        return True
    if service is None:
        st.warning("开发者模式暂时不可用。")
        return False
    enabled = service.is_enabled(principal)
    if enabled:
        st.success("开发者模式已启用；原平台套餐和系统 AI 额度保持不变。")
        if st.button("关闭开发者模式", key=f"{key_prefix}_disable_byok"):
            service.set_enabled(principal, False)
            st.session_state.principal = principal.model_copy(
                update={"byok_enabled": False}
            )
            st.rerun()
    elif st.button("启用开发者模式", key=f"{key_prefix}_enable_byok", type="primary"):
        service.set_enabled(principal, True)
        st.session_state.principal = principal.model_copy(update={"byok_enabled": True})
        st.rerun()
    return enabled
