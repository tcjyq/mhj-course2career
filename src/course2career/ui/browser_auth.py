"""Opaque browser cookie boundary for server-side authentication sessions."""

from datetime import UTC, datetime, timedelta

import extra_streamlit_components as stx
import streamlit as st

AUTH_COOKIE = "c2c_auth_session"


def cookie_manager() -> stx.CookieManager:
    return stx.CookieManager(key="c2c_auth_cookie_reader")


def read_token(manager: stx.CookieManager) -> str | None:
    # Request cookies are available immediately on a fresh WebSocket session.
    # The component's getAll result is asynchronous and may be empty initially.
    token = st.context.cookies.get(AUTH_COOKIE) or manager.get(AUTH_COOKIE)
    return token if isinstance(token, str) else None


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
