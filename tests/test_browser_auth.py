from datetime import UTC, datetime
from unittest.mock import Mock

from course2career.ui.browser_auth import AUTH_COOKIE, clear_token, set_token


def test_production_cookie_is_opaque_scoped_and_expires():
    manager = Mock()
    token = "A" * 43
    before = datetime.now(UTC)
    set_token(manager, token, production=True)
    args, kwargs = manager.set.call_args
    assert args == (AUTH_COOKIE, token)
    assert kwargs["secure"] is True
    assert kwargs["same_site"] == "strict"
    assert kwargs["path"] == "/"
    assert 6.99 < (kwargs["expires_at"] - before).total_seconds() / 86400 < 7.01
    assert "token" not in kwargs


def test_local_cookie_and_delete_are_safe_when_cache_is_empty():
    manager = Mock()
    set_token(manager, "B" * 43, production=False)
    assert manager.set.call_args.kwargs["secure"] is False
    manager.delete.side_effect = KeyError(AUTH_COOKIE)
    clear_token(manager)
    manager.delete.assert_called_once_with(AUTH_COOKIE, key="c2c_auth_cookie_delete")
