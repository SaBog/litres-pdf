import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
from litres.loaders.base_loader import BaseLoaderCommand
from litres.models.book import Book
from litres.models.output_path_handler import OutputPathHandler
from litres.exceptions import BookProcessingError
import requests

class DummyLoader(BaseLoaderCommand[Book]):
    def _download_part(self, part_num, book, source_dir):
        return True
    def fetch(self, url, delay=0.1):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        return response

def test_look_for_loaded_content(tmp_path):
    (tmp_path / "1").write_text("a")
    (tmp_path / "2").write_text("b")
    (tmp_path / "foo").write_text("c")
    loader = DummyLoader(MagicMock())
    result = loader.look_for_loaded_content(tmp_path)
    assert result == [1, 2]
    result = loader.look_for_loaded_content(tmp_path, except_filename="2")
    assert result == [1]

def test_download_parts_all_downloaded(monkeypatch):
    loader = DummyLoader(MagicMock())
    book = MagicMock(total_parts=2)
    path = MagicMock()
    path.source = Path("/tmp")
    monkeypatch.setattr(loader, "look_for_loaded_content", lambda d, except_filename=None: [0, 1])
    with patch("litres.loaders.base_loader.logger.info") as log_info:
        loader.download_parts(book, path)
        log_info.assert_called()

def test_download_parts_missing_parts(monkeypatch):
    loader = DummyLoader(MagicMock())
    book = MagicMock(total_parts=2)
    path = MagicMock()
    path.source = Path("/tmp")
    # Simulate missing part 1
    monkeypatch.setattr(loader, "look_for_loaded_content", lambda d, except_filename=None: [0])
    monkeypatch.setattr(loader, "_download_part", lambda part_num, book, source: True)
    with patch("litres.loaders.base_loader.logger.info"), \
         patch("litres.loaders.base_loader.tqdm"), \
         patch("litres.loaders.base_loader.ThreadPoolExecutor") as executor:
        instance = executor.return_value.__enter__.return_value
        instance.submit.return_value = MagicMock()
        instance.submit.return_value.result.return_value = True
        instance.submit.side_effect = lambda fn, *args, **kwargs: MagicMock(result=lambda: True)
        instance.__iter__.return_value = [instance.submit.return_value]
        monkeypatch.setattr(loader, "look_for_loaded_content", lambda d, except_filename=None: [0, 1])
        loader.download_parts(book, path)

def test_download_part_not_implemented():
    loader = BaseLoaderCommand[Book](MagicMock())
    with pytest.raises(NotImplementedError):
        loader._download_part(0, MagicMock(), Path("/tmp"))

def test_fetch_with_retry_success(monkeypatch):
    loader = DummyLoader(MagicMock())
    monkeypatch.setattr(loader, "fetch", lambda url, delay=0.1: MagicMock())
    resp = loader._fetch_with_retry("url", Path("/tmp"))
    assert resp

def test_fetch_with_retry_429(monkeypatch):
    loader = DummyLoader(MagicMock())
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {"Retry-After": "1"}
    def fetch(url, delay=0.1):
        raise requests.exceptions.HTTPError(response=resp)
    monkeypatch.setattr(loader, "fetch", fetch)
    with patch("litres.loaders.base_loader.logger.warning") as log_warn:
        with pytest.raises(RuntimeError):
            loader._fetch_with_retry("url", Path("/tmp"), max_attempts=1)
        log_warn.assert_called()

def test_fetch_with_retry_network_error(monkeypatch):
    loader = DummyLoader(MagicMock())
    def fetch(url, delay=0.1):
        raise requests.exceptions.RequestException("fail")
    monkeypatch.setattr(loader, "fetch", fetch)
    with patch("litres.loaders.base_loader.logger.warning") as log_warn:
        with pytest.raises(RuntimeError):
            loader._fetch_with_retry("url", Path("/tmp"), max_attempts=1)
        log_warn.assert_called()
