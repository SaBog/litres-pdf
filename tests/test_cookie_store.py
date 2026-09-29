import json

from litres.services.cookie_store import CookieStore


def test_load_missing_file_returns_empty(tmp_path, mocker):
    warn = mocker.patch("litres.services.cookie_store.logger.warning")
    assert CookieStore(tmp_path / "cookies.json").load() == []
    warn.assert_called_once()


def test_load_returns_stored_cookies(tmp_path):
    path = tmp_path / "cookies.json"
    path.write_text(json.dumps([{"name": "SID", "value": "1"}]), encoding="utf-8")
    assert CookieStore(path).load() == [{"name": "SID", "value": "1"}]


def test_load_corrupt_file_returns_empty_and_logs(tmp_path, mocker):
    path = tmp_path / "cookies.json"
    path.write_text("{not json", encoding="utf-8")
    error = mocker.patch("litres.services.cookie_store.logger.error")
    assert CookieStore(path).load() == []
    error.assert_called_once()


def test_save_keeps_only_sid_and_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "cookies.json"
    store = CookieStore(path)

    saved = store.save([{"name": "OTHER", "value": "x"}, {"name": "SID", "value": "1"}])

    assert saved is True
    assert json.loads(path.read_text(encoding="utf-8")) == [
        {"name": "SID", "value": "1"}
    ]
    assert store.load() == [{"name": "SID", "value": "1"}]


def test_save_without_sid_writes_nothing(tmp_path, mocker):
    path = tmp_path / "cookies.json"
    warn = mocker.patch("litres.services.cookie_store.logger.warning")
    assert CookieStore(path).save([{"name": "OTHER", "value": "x"}]) is False
    assert not path.exists()
    warn.assert_called_once()


def test_save_write_error_returns_false_and_logs(tmp_path, mocker):
    error = mocker.patch("litres.services.cookie_store.logger.error")
    # a directory where the file should be makes the write fail
    path = tmp_path / "cookies.json"
    path.mkdir()
    assert CookieStore(path).save([{"name": "SID", "value": "1"}]) is False
    error.assert_called_once()
