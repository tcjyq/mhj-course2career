"""First-party browser storage for opaque, server-validated auth tokens."""

import logging
from dataclasses import dataclass
from typing import Literal

import streamlit as st

AUTH_STORAGE_KEY = "c2c_auth_session"
_LOGGER = logging.getLogger(__name__)

_STORAGE_JS = """
export default function (component) {
  const { data, setStateValue } = component;
  const key = "c2c_auth_session";
  const clearLegacyCookie = () => {
    const secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${key}=; Max-Age=0; Path=/; SameSite=Strict${secure}`;
  };
  const legacyCookie = () => {
    const prefix = `${key}=`;
    for (const part of document.cookie.split(";")) {
      const item = part.trim();
      if (item.startsWith(prefix)) {
        try { return decodeURIComponent(item.slice(prefix.length)); }
        catch (_) { return null; }
      }
    }
    return null;
  };
  let token = null;
  let ok = true;
  try {
    if (data.action === "clear") {
      localStorage.removeItem(key);
      clearLegacyCookie();
    } else if (data.action === "set") {
      if (/^[A-Za-z0-9_-]{43}$/.test(data.token || "")) {
        localStorage.setItem(key, data.token);
        clearLegacyCookie();
      } else {
        ok = false;
      }
    } else {
      token = localStorage.getItem(key);
      if (!token) {
        const oldToken = legacyCookie();
        if (oldToken) {
          localStorage.setItem(key, oldToken);
          clearLegacyCookie();
        }
      }
    }
    token = localStorage.getItem(key);
  } catch (_) {
    ok = false;
    token = null;
  }
  setStateValue("storage", {
    ready: true, token: token, nonce: data.nonce, ok: ok,
  });
}
"""

_STORAGE_COMPONENT = st.components.v2.component(
    "course2career_auth_storage", js=_STORAGE_JS
)


@dataclass(frozen=True)
class BrowserStorageState:
    phase: Literal["PENDING", "TOKEN_PRESENT", "NO_TOKEN"]
    token: str | None = None
    ok: bool = True


def parse_storage_state(value: object, *, nonce: str) -> BrowserStorageState:
    if (
        not isinstance(value, dict)
        or value.get("ready") is not True
        or value.get("nonce") != nonce
    ):
        return BrowserStorageState("PENDING")
    token = value.get("token")
    if isinstance(token, str) and token:
        return BrowserStorageState("TOKEN_PRESENT", token, value.get("ok") is True)
    return BrowserStorageState("NO_TOKEN", ok=value.get("ok") is True)


def log_restore_state(
    state: BrowserStorageState,
    *,
    server_session_found: bool,
    restore_result: Literal["authenticated", "guest", "pending"],
) -> None:
    """Only fixed states and booleans may reach production logs."""
    _LOGGER.warning(
        "auth_restore_start storage_ready=%s storage_ok=%s "
        "storage_token_present=%s server_session_found=%s restore_result=%s",
        state.phase != "PENDING",
        state.ok,
        state.phase == "TOKEN_PRESENT",
        bool(server_session_found),
        restore_result,
    )


def read_browser_storage(
    *, action: Literal["read", "set", "clear"], nonce: str, token: str | None = None
) -> BrowserStorageState:
    data = {"action": action, "nonce": nonce}
    if action == "set":
        data["token"] = token
    result = _STORAGE_COMPONENT(
        key="c2c_auth_storage", data=data, on_storage_change=lambda: None
    )
    return parse_storage_state(getattr(result, "storage", None), nonce=nonce)
