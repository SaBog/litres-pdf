from unittest.mock import MagicMock

import pytest
import requests

from litres.exceptions import BookProcessingError
from litres.services.litres_api import API_BASE, LitresApi


def make_session(cookies=None):
    session = MagicMock(spec=requests.Session)
    session.cookies = MagicMock()
    session.cookies.get.side_effect = lambda name: (cookies or {}).get(name)
    return session


def response(json_body=None, headers=None):
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.headers = headers or {}
    return resp


def make_api(cookies=None, content_session=None):
    session = make_session(cookies)
    return LitresApi(session, content_session or MagicMock()), session


def test_requests_carry_the_reader_headers_and_session_cookies():
    api, session = make_api({"SID": "sid-1", "supersid": "super-1"})
    session.get.return_value = response({"status": 200, "payload": {"data": {"link": "L"}}})

    api.file_link("39305103", page_id=2)

    headers = session.get.call_args.kwargs["headers"]
    assert headers["App-Id"] == "115"
    assert headers["Client-host"] == "www.litres.ru"
    assert headers["Session-Id"] == "sid-1"
    assert headers["supersid"] == "super-1"
    assert headers["Ui-Language-Code"] == "ru"
    assert headers["ui-currency"] == "RUB"


def test_headers_omit_cookies_that_are_not_set():
    api, session = make_api({})
    session.get.return_value = response({"status": 200, "payload": {"data": {"link": "L"}}})

    api.file_link("1")

    headers = session.get.call_args.kwargs["headers"]
    assert "Session-Id" not in headers
    assert "supersid" not in headers


def test_file_link_returns_signed_link_and_passes_query():
    api, session = make_api({"SID": "s"})
    session.get.return_value = response(
        {"status": 200, "error": None, "payload": {"data": {"link": "https://content/x"}}}
    )

    link = api.file_link(
        "39305103", page_id=2, is_trial="false", resolution="w1900", image_type="gif"
    )

    assert link == "https://content/x"
    url = session.get.call_args.args[0]
    assert url == f"{API_BASE}/arts/files/39305103/link"
    assert session.get.call_args.kwargs["params"] == {
        "page_id": 2,
        "is_trial": "false",
        "resolution": "w1900",
        "image_type": "gif",
    }


@pytest.mark.parametrize(
    "body",
    [
        {"status": 403, "payload": {"data": {"link": "L"}}},
        {"status": 200, "payload": {"data": {}}},
        {"status": 200, "payload": None},
        {"status": 200},
    ],
)
def test_file_link_rejects_unexpected_bodies(body):
    api, session = make_api()
    session.get.return_value = response(body)
    with pytest.raises(BookProcessingError, match="Unexpected link response"):
        api.file_link("1")


def test_file_link_propagates_http_errors():
    api, session = make_api()
    session.get.return_value.raise_for_status.side_effect = requests.HTTPError("401")
    with pytest.raises(requests.HTTPError):
        api.file_link("1")


def test_drm_params_parse_the_drm3_key_header_and_are_cached():
    api, session = make_api({"SID": "s"})
    session.get.return_value = response(headers={"Drm3-Key": "1790965451:abcDEF"})

    assert api.drm_params("25030016") == {"timestamp": "1790965451", "md5": "abcDEF"}
    assert api.drm_params("25030016") == {"timestamp": "1790965451", "md5": "abcDEF"}

    session.get.assert_called_once()
    assert session.get.call_args.args[0] == f"{API_BASE}/arts/25030016"


@pytest.mark.parametrize("header", ["", "0:abc", "123:", "garbage", "x:abc"])
def test_drm_params_empty_when_the_key_is_missing_or_malformed(header):
    api, session = make_api()
    session.get.return_value = response(headers={"Drm3-Key": header} if header else {})
    assert api.drm_params("1") == {}


def test_drm_params_without_art_id_makes_no_request():
    api, session = make_api()
    assert api.drm_params(None) == {}
    session.get.assert_not_called()


def test_drm_failure_is_swallowed_like_the_reader_does(mocker):
    api, session = make_api()
    session.get.side_effect = requests.ConnectionError("down")
    warn = mocker.patch("litres.services.litres_api.logger.warning")

    assert api.drm_params("1") == {}
    warn.assert_called_once()


def test_reset_drm_forces_a_new_signature_request():
    api, session = make_api()
    session.get.return_value = response(headers={"Drm3-Key": "5:aa"})

    api.drm_params("1")
    api.reset_drm()
    api.drm_params("1")

    assert session.get.call_count == 2


def test_download_uses_the_anonymous_content_session():
    content = MagicMock()
    api, session = make_api({"SID": "secret"}, content_session=content)

    result = api.download("https://content.litres.ru/download_book?x=1")

    assert result is content.get.return_value
    content.get.assert_called_once()
    assert content.get.call_args.kwargs["stream"] is True
    session.get.assert_not_called()  # the authenticated session is not used
    assert "headers" not in content.get.call_args.kwargs  # no SID leaks to content host


def test_default_content_session_has_no_credentials():
    api = LitresApi(make_session({"SID": "secret"}))
    content = api._content_session
    assert "session-id" not in {k.lower() for k in content.headers}
    assert len(content.cookies) == 0
