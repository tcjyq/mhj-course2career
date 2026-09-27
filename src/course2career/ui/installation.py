"""Independent first-party installation marker; never a human identity."""

from dataclasses import dataclass
from typing import Literal

import streamlit as st

from course2career.installation_identity import installation_hash

_STORAGE_JS = """
export default function (component) {
  const key = "c2c_installation_id";
  let value = null;
  try {
    value = localStorage.getItem(key);
    if (!/^[A-Za-z0-9_-]{43}$/.test(value || "")) {
      const bytes = new Uint8Array(32);
      crypto.getRandomValues(bytes);
      value = btoa(String.fromCharCode(...bytes))
        .replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
      localStorage.setItem(key, value);
    }
    component.setStateValue("installation", {ready: true, value: value});
  } catch (_) {
    component.setStateValue("installation", {ready: true, unavailable: true});
  }
}
"""
_INSTALLATION_COMPONENT = st.components.v2.component(
    "course2career_installation", js=_STORAGE_JS
)


@dataclass(frozen=True)
class InstallationState:
    phase: Literal["PENDING", "PRESENT", "UNAVAILABLE"]
    value: str | None = None


def parse_installation_state(value: object) -> InstallationState:
    if not isinstance(value, dict) or value.get("ready") is not True:
        return InstallationState("PENDING")
    raw = value.get("value")
    if installation_hash(raw) is not None:
        return InstallationState("PRESENT", raw)
    return InstallationState("UNAVAILABLE")


def read_installation() -> InstallationState:
    try:
        result = _INSTALLATION_COMPONENT(
            key="c2c_installation_storage", on_installation_change=lambda: None
        )
    except Exception:
        return InstallationState("UNAVAILABLE")
    return parse_installation_state(getattr(result, "installation", None))
