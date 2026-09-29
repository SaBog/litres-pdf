from unittest.mock import MagicMock

import pytest

from litres.engines.base import Engine
from litres.exceptions import BookProcessingError
from litres.handlers.book_handler import BookHandler
from litres.models.book import Author, Book, BookFormat, BookMeta, BookRequest
from litres.models.out_format import OutFormat


class FakeEngine(Engine[Book]):
    def __init__(self, fmt: OutFormat):
        self.SUPPORTED_OUT_FORMAT = fmt
        self.executed_with: tuple | None = None

    def execute(self, book, path):
        self.executed_with = (book, path)


def make_book(title="My: Book") -> Book:
    meta = BookMeta(authors=[Author(first="A")], title=title, version=1.0, uuid="u")
    return Book(meta=meta, parts=[])


def make_handler(tmp_path, engines, extractor=None, loader=None) -> BookHandler[Book]:
    return BookHandler(
        extractor or MagicMock(),
        loader or MagicMock(),
        engines,
        tmp_path / "source",
        tmp_path / "books",
    )


def test_load_extracts_then_downloads_into_sanitized_paths(tmp_path):
    book = make_book("My: Book")
    extractor, loader = MagicMock(), MagicMock()
    extractor.get.return_value = book
    handler = make_handler(tmp_path, [], extractor, loader)
    bq = BookRequest(url="u", format=BookFormat.O3)

    handler.load(bq)

    extractor.get.assert_called_once_with(bq)
    loader.download_parts.assert_called_once()
    downloaded_book, paths = loader.download_parts.call_args.args
    assert downloaded_book is book
    assert paths.filename == "My_ Book"
    assert paths.source == tmp_path / "source" / "My_ Book"
    assert paths.output == tmp_path / "books"


def test_save_uses_first_engine_matching_priority(tmp_path):
    pdf, fb2 = FakeEngine(OutFormat.PDF), FakeEngine(OutFormat.FB2)
    handler = make_handler(tmp_path, [pdf, fb2])
    handler.book = make_book()

    handler.save([OutFormat.FB2, OutFormat.PDF])

    assert fb2.executed_with is not None
    assert pdf.executed_with is None


def test_save_without_matching_engine_raises(tmp_path):
    handler = make_handler(tmp_path, [FakeEngine(OutFormat.PDF)])
    handler.book = make_book()
    with pytest.raises(BookProcessingError):
        handler.save([OutFormat.MP3])


def test_engine_failure_propagates_and_nothing_is_reported_as_saved(tmp_path, mocker):
    engine = FakeEngine(OutFormat.PDF)
    engine.execute = MagicMock(side_effect=BookProcessingError("boom"))
    handler = make_handler(tmp_path, [engine])
    handler.book = make_book()
    log = mocker.patch("litres.handlers.book_handler.logger")

    with pytest.raises(BookProcessingError):
        handler.save([OutFormat.PDF])

    assert not any("saved" in str(c) for c in log.info.call_args_list)
