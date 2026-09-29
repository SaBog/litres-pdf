from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from litres.loaders.base_loader import BaseLoader
from litres.models.book import Book


class DummyLoader(BaseLoader[Book]):
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


def test_download_parts_all_downloaded(monkeypatch):
    loader = DummyLoader(MagicMock())
    book = MagicMock(total_parts=2)
    path = MagicMock()
    path.source = Path("/tmp")
    monkeypatch.setattr(loader, "look_for_loaded_content", lambda d: [0, 1])
    with patch("litres.loaders.base_loader.logger.info") as log_info:
        loader.download_parts(book, path)
        log_info.assert_called()


def test_download_parts_missing_parts(monkeypatch):
    loader = DummyLoader(MagicMock())
    book = MagicMock(total_parts=2)
    path = MagicMock()
    path.source = Path("/tmp")
    # Simulate missing part 1
    monkeypatch.setattr(loader, "look_for_loaded_content", lambda d: [0])
    monkeypatch.setattr(loader, "_download_part", lambda part_num, book, source: True)
    with (
        patch("litres.loaders.base_loader.logger.info"),
        patch("litres.loaders.base_loader.tqdm"),
        patch("litres.loaders.base_loader.ThreadPoolExecutor") as executor,
    ):
        instance = executor.return_value.__enter__.return_value
        instance.submit.return_value = MagicMock()
        instance.submit.return_value.result.return_value = True
        instance.submit.side_effect = lambda fn, *args, **kwargs: MagicMock(
            result=lambda: True
        )
        instance.__iter__.return_value = [instance.submit.return_value]
        monkeypatch.setattr(loader, "look_for_loaded_content", lambda d: [0, 1])
        loader.download_parts(book, path)


def test_loader_without_download_part_cannot_be_instantiated():
    class Incomplete(BaseLoader[Book]):
        pass

    with pytest.raises(TypeError, match="_download_part"):
        Incomplete(MagicMock())  # ty: ignore[call-non-callable]


def test_fetch_with_retry_success(monkeypatch):
    loader = DummyLoader(MagicMock())
    monkeypatch.setattr(loader, "fetch", lambda url, delay=0.1: MagicMock())
    resp = loader._fetch_with_retry("url")
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
            loader._fetch_with_retry("url", max_attempts=1)
        log_warn.assert_called()


def test_fetch_with_retry_network_error(monkeypatch):
    loader = DummyLoader(MagicMock())

    def fetch(url, delay=0.1):
        raise requests.exceptions.RequestException("fail")

    monkeypatch.setattr(loader, "fetch", fetch)
    with patch("litres.loaders.base_loader.logger.warning") as log_warn:
        with pytest.raises(RuntimeError):
            loader._fetch_with_retry("url", max_attempts=1)
        log_warn.assert_called()


def test_atomic_write_leaves_no_file_on_failure(tmp_path):
    def broken_chunks():
        yield b"partial"
        raise ConnectionError("dropped")

    target = tmp_path / "0.pdf"
    with pytest.raises(ConnectionError):
        BaseLoader._atomic_write(target, broken_chunks())

    assert list(tmp_path.iterdir()) == []
    assert DummyLoader(MagicMock()).look_for_loaded_content(tmp_path) == []


def test_atomic_write_success_replaces_file(tmp_path):
    target = tmp_path / "0.pdf"
    target.write_bytes(b"old")
    BaseLoader._atomic_write(target, [b"ne", b"w"])
    assert target.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["0.pdf"]


def test_in_progress_part_files_are_not_counted_as_loaded(tmp_path):
    (tmp_path / "0.txt").write_text("done")
    (tmp_path / "1.txt.123.456.part").write_text("half")
    loader = DummyLoader(MagicMock())
    assert loader.look_for_loaded_content(tmp_path) == [0]


def test_save_response_closes_response(tmp_path):
    response = MagicMock()
    response.iter_content.return_value = [b"a", b"b"]
    DummyLoader(MagicMock())._save_response(response, tmp_path / "0.mp3")
    assert (tmp_path / "0.mp3").read_bytes() == b"ab"
    response.close.assert_called_once()


def test_rate_limiter_spaces_requests_across_threads():
    import threading
    import time

    from litres.loaders.base_loader import RateLimiter

    limiter = RateLimiter()
    starts: list[float] = []
    lock = threading.Lock()

    def worker():
        limiter.wait(0.05)
        with lock:
            starts.append(time.monotonic())

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    starts.sort()
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(gap >= 0.04 for gap in gaps)


def test_rate_limiter_penalty_delays_next_request():
    import time

    from litres.loaders.base_loader import RateLimiter

    limiter = RateLimiter()
    limiter.penalize(0.1)
    begin = time.monotonic()
    limiter.wait(0.01)
    assert time.monotonic() - begin >= 0.09


def test_fetch_with_retry_429_pauses_all_threads(monkeypatch):
    loader = DummyLoader(MagicMock())
    resp = MagicMock(status_code=429, headers={"Retry-After": "7"})
    calls = []

    def fetch(url, delay=0.1):
        raise requests.exceptions.HTTPError(response=resp)

    monkeypatch.setattr(loader, "fetch", fetch)
    monkeypatch.setattr(loader._rate_limiter, "penalize", calls.append)
    with pytest.raises(RuntimeError):
        loader._fetch_with_retry("url", max_attempts=1)
    assert calls == [7.0]


def test_retry_after_with_garbage_header_falls_back_to_default(monkeypatch):
    loader = DummyLoader(MagicMock())
    resp = MagicMock(status_code=429, headers={"Retry-After": "Wed, 21 Oct 2026"})
    calls = []

    def fetch(url, delay=0.1):
        raise requests.exceptions.HTTPError(response=resp)

    monkeypatch.setattr(loader, "fetch", fetch)
    monkeypatch.setattr(loader._rate_limiter, "penalize", calls.append)
    with pytest.raises(RuntimeError):
        loader._fetch_with_retry("url", max_attempts=1)
    assert calls == [15]


def test_download_parts_uses_injected_max_workers(tmp_path):
    from concurrent.futures import ThreadPoolExecutor as RealExecutor

    used = []

    def spy_executor(max_workers):
        used.append(max_workers)
        return RealExecutor(max_workers=max_workers)

    class OneFileLoader(DummyLoader):
        def _download_part(self, part_num, book, source_dir):
            (source_dir / str(part_num)).write_text("x")
            return True

    path = MagicMock()
    path.source = tmp_path
    with patch("litres.loaders.base_loader.ThreadPoolExecutor", spy_executor):
        loader = OneFileLoader(MagicMock(), max_workers=3)
        loader.download_parts(MagicMock(total_parts=2), path)

    assert used == [3]


def test_loader_passes_injected_delay_to_fetch(monkeypatch):
    seen = []
    loader = DummyLoader(MagicMock(), delay=0.75)
    monkeypatch.setattr(loader, "fetch", lambda url, delay=0: seen.append(delay))
    loader._fetch_with_retry("url")
    assert seen == [0.75]
