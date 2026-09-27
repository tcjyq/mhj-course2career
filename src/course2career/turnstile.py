"""Server-only Turnstile Siteverify boundary for public registration."""

from dataclasses import dataclass, field

import httpx

from course2career.config import Settings

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TEST_SITE_KEY = "1x00000000000000000000AA"
TEST_SECRET_KEY = "1x0000000000000000000000000000000AA"


class TurnstileError(ValueError):
    """The challenge could not be validated; never include its token."""


@dataclass(frozen=True)
class TurnstileVerifier:
    secret_key: str | None = field(repr=False)
    allowed_hostnames: tuple[str, ...]
    client: httpx.Client | None = field(default=None, repr=False)

    def validate(self, token: str | None) -> None:
        if (
            not self.secret_key
            or not self.allowed_hostnames
            or not isinstance(token, str)
            or not token
            or len(token) > 2048
        ):
            raise TurnstileError("暂时无法完成注册，请刷新后重试。")
        sender = self.client or httpx
        try:
            response = sender.post(
                SITEVERIFY_URL,
                data={"secret": self.secret_key, "response": token},
                timeout=5.0,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError):
            raise TurnstileError("暂时无法完成注册，请稍后再试。") from None
        if (
            not isinstance(result, dict)
            or result.get("success") is not True
            or result.get("hostname") not in self.allowed_hostnames
            or result.get("action") != "register"
        ):
            raise TurnstileError("验证未通过，请重试。")


def build_registration_verifier(settings: Settings) -> TurnstileVerifier:
    """Use a deterministic dummy-token Siteverify only in local test mode."""
    if (
        not settings.production_mode
        and settings.turnstile_site_key == TEST_SITE_KEY
        and settings.turnstile_secret_key == TEST_SECRET_KEY
    ):

        def local_response(request: httpx.Request) -> httpx.Response:
            valid = b"XXXX.DUMMY.TOKEN.XXXX" in request.content
            return httpx.Response(
                200,
                json={
                    "success": valid,
                    "hostname": "localhost",
                    "action": "register",
                },
            )

        return TurnstileVerifier(
            TEST_SECRET_KEY,
            settings.turnstile_allowed_hostnames,
            httpx.Client(transport=httpx.MockTransport(local_response)),
        )
    return TurnstileVerifier(
        settings.turnstile_secret_key, settings.turnstile_allowed_hostnames
    )
