from unittest.mock import MagicMock

import pytest
import requests

from litres.constants import DOMAIN
from litres.services.auth_service import USER_AGENT, AuthService, create_session

SID = {"name": "SID", "value": "sid-1", "domain": ".litres.ru"}


def make_service(stored=None, login_cookies=None, api_status=200):
    """AuthService with a fake store/login and a scripted LitRes API response."""
    store = MagicMock()
    stored_now = list(stored or [])
    store.load.side_effect = lambda: list(stored_now)

    def save(cookies):
        stored_now[:] = [c for c in cookies if c["name"] == "SID"]
        return True

    store.save.side_effect = save
    login = MagicMock()
    login.run.return_value = login_cookies

    session = requests.Session()
    response = MagicMock(status_code=api_status)
    session.get = MagicMock(return_value=response)
    return AuthService(store, login, session), store, login, session


def test_create_session_sets_default_headers():
    headers = create_session().headers
    assert headers["user-agent"] == USER_AGENT
    assert headers["referer"] == DOMAIN
    assert headers["accept"] == "*/*"


def test_sessions_retry_dropped_connections_and_gateway_errors():
    retry = create_session().get_adapter("https://api.litres.ru").max_retries

    assert retry.total == 3
    assert set(retry.status_forcelist) == {502, 503, 504}
    assert 429 not in retry.status_forcelist  # the loaders pause all workers instead
    assert retry.allowed_methods is not None
    assert "POST" not in retry.allowed_methods


def test_valid_saved_cookie_authenticates_without_browser():
    auth, _, login, session = make_service(stored=[SID])

    assert auth.authenticate() is True
    assert auth.is_authenticated is True
    login.run.assert_not_called()
    assert session.headers["session-id"] == "sid-1"
    assert session.get.call_args.args[0].endswith("/users/me")


def test_no_saved_cookie_goes_to_browser_login_and_saves_sid():
    auth, store, login, session = make_service(
        stored=[], login_cookies=[SID, {"name": "OTHER", "value": "x"}]
    )

    assert auth.authenticate() is True
    login.run.assert_called_once()
    store.save.assert_called_once()
    assert session.headers["session-id"] == "sid-1"
    assert session.cookies.get("OTHER") is None  # only the saved SID is applied


def test_rejected_saved_cookie_falls_back_to_browser_login():
    auth, _, login, _ = make_service(stored=[SID], login_cookies=[SID], api_status=401)

    assert auth.authenticate() is False  # still rejected after login
    login.run.assert_called_once()


def test_failed_browser_login_leaves_service_unauthenticated():
    auth, store, _, _ = make_service(stored=[], login_cookies=None)

    assert auth.authenticate() is False
    assert auth.is_authenticated is False
    store.save.assert_not_called()


def test_session_property_requires_authentication():
    auth, *_ = make_service()
    with pytest.raises(RuntimeError, match="Session is not authenticated"):
        _ = auth.session


def test_session_property_after_authentication():
    auth, _, _, session = make_service(stored=[SID])
    auth.authenticate()
    assert auth.session is session


def test_check_authentication_without_sid_makes_no_request():
    auth, _, _, session = make_service()
    assert auth._check_authentication() is False
    session.get.assert_not_called()


def test_check_authentication_network_error_is_reported_as_failure(mocker):
    auth, _, _, session = make_service(stored=[SID])
    auth._apply_cookies([SID])
    session.get.side_effect = Exception("Network error")
    error = mocker.patch("litres.services.auth_service.logger.error")

    assert auth._check_authentication() is False
    error.assert_called_once()


def test_apply_cookies_uses_defaults_for_missing_fields():
    auth, _, _, session = make_service()
    auth._apply_cookies([{"name": "SID", "value": "9"}])
    cookie = next(iter(session.cookies))
    assert (cookie.name, cookie.value, cookie.path) == ("SID", "9", "/")


def test_apply_cookies_without_sid_removes_stale_header():
    auth, _, _, session = make_service()
    session.headers["session-id"] = "stale"
    auth._apply_cookies([])
    assert "session-id" not in session.headers
