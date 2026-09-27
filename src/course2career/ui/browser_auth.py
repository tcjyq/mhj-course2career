"""Opaque browser cookie boundary for server-side authentication sessions."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import extra_streamlit_components as stx
import streamlit as st

AUTH_COOKIE = "c2c_auth_session"
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CookieReadState:
    token: str | None
    context_cookie_present: bool
    component_cookie_ready: bool
    component_token_present: bool


def cookie_manager() -> stx.CookieManager:
    return stx.CookieManager(key="c2c_auth_cookie_reader")


def read_token(manager: stx.CookieManager) -> CookieReadState:
    # Request cookies are available immediately on a fresh WebSocket session.
    # The component's getAll result is asynchronous and may be empty initially.
    try:
        context_token = st.context.cookies.get(AUTH_COOKIE)
    except Exception:
        context_token = None
    component_token = manager.get(AUTH_COOKIE)
    token = context_token or component_token
    return CookieReadState(
        token=token if isinstance(token, str) else None,
        context_cookie_present=bool(context_token),
        component_cookie_ready=isinstance(
            st.session_state.get("c2c_auth_cookie_reader"), dict
        ),
        component_token_present=bool(component_token),
    )


def log_restore_state(
    source: CookieReadState,
    *,
    server_session_found: bool,
    restore_result: str,
) -> None:
    """Log only fixed state and boolean fields; never pass token to logging."""
    result = (
        restore_result
        if restore_result in {"authenticated", "guest", "pending"}
        else "guest"
    )
    _LOGGER.warning(
        "auth_restore_start context_cookie_present=%s "
        "component_cookie_ready=%s component_token_present=%s "
        "server_session_found=%s restore_result=%s",
        source.context_cookie_present,
        source.component_cookie_ready,
        source.component_token_present,
        bool(server_session_found),
        result,
    )


def set_token(manager: stx.CookieManager, token: str, *, production: bool) -> None:
    manager.set(
        AUTH_COOKIE,
        token,
        key="c2c_auth_cookie_set",
        path="/",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        secure=production,
        same_site="strict",
    )


def clear_token(manager: stx.CookieManager) -> None:
    try:
        manager.delete(AUTH_COOKIE, key="c2c_auth_cookie_delete")
    except KeyError:
        # The library queues the browser deletion before updating its local cache.
        pass
