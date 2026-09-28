"""A registration-only Turnstile widget; its token stays in Streamlit state."""

import streamlit as st

_WIDGET_JS = """
export default function (component) {
  const {data, setStateValue, parentElement} = component;
  const holder = document.createElement("div");
  parentElement.appendChild(holder);
  let widget = null;
  let cancelled = false;
  const publish = (token) => setStateValue("challenge", {
    ready: true, token: token || null, nonce: data.nonce
  });
  const render = () => {
    if (cancelled) return;
    widget = window.turnstile.render(holder, {
      sitekey: data.sitekey, action: "register", size: "flexible",
      callback: publish,
      "expired-callback": () => publish(null),
      "error-callback": () => publish(null)
    });
    publish(null);
  };
  if (window.turnstile) render();
  else {
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.onload = render;
    script.onerror = () => publish(null);
    document.head.appendChild(script);
  }
  return () => {
    cancelled = true;
    if (widget !== null && window.turnstile) window.turnstile.remove(widget);
    holder.remove();
  };
}
"""
_WIDGET = st.components.v2.component(
    "course2career_turnstile", js=_WIDGET_JS, isolate_styles=False
)


def read_registration_challenge(site_key: str | None, *, nonce: str) -> str | None:
    if not site_key:
        return None
    try:
        result = _WIDGET(
            key="c2c_registration_turnstile",
            data={"sitekey": site_key, "nonce": nonce},
            on_challenge_change=lambda: None,
        )
    except Exception:
        return None
    challenge = getattr(result, "challenge", None)
    if not isinstance(challenge, dict) or challenge.get("nonce") != nonce:
        return None
    token = challenge.get("token")
    return token if isinstance(token, str) and 0 < len(token) <= 2048 else None
