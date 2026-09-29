from unittest.mock import MagicMock

from litres.engines.base import Engine
from litres.handlers.book_handler import BookHandler
from litres.models.book import Author, Book, BookFormat, BookMeta, BookRequest
from litres.models.out_format import OutFormat


class RecordingEngine(Engine[Book]):
    SUPPORTED_OUT_FORMAT = OutFormat.PDF

    def execute(self, book, path):
        self.output_existed = path.output.is_dir()


def make_book(title="Title") -> Book:
    meta = BookMeta(authors=[Author(first="A")], title=title, version=1.0, uuid="u")
    return Book(meta=meta, parts=[])


def make_handler(tmp_path, engines=(), extractor=None, loader=None):
    return BookHandler(
        extractor or MagicMock(),
        loader or MagicMock(),
        list(engines),
        tmp_path / "source",
        tmp_path / "books",
    )


def test_constructing_a_handler_touches_no_directories(tmp_path):
    make_handler(tmp_path)
    assert not (tmp_path / "source").exists()
    assert not (tmp_path / "books").exists()


def test_load_creates_directories_before_downloading(tmp_path):
    extractor, loader = MagicMock(), MagicMock()
    extractor.get.return_value = make_book("Title")
    seen = {}
    loader.download_parts.side_effect = lambda book, paths: seen.update(
        source=paths.source.is_dir(), output=paths.output.is_dir()
    )

    make_handler(tmp_path, extractor=extractor, loader=loader).load(
        BookRequest(url="u", format=BookFormat.O3)
    )

    assert seen == {"source": True, "output": True}


def test_save_creates_output_directory_for_the_engine(tmp_path):
    engine = RecordingEngine()
    handler = make_handler(tmp_path, [engine])
    handler.book = make_book("Title")

    handler.save([OutFormat.PDF])

    assert engine.output_existed is True
