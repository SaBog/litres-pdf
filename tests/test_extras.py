from unittest.mock import MagicMock

import pytest
import requests

from litres.exceptions import BookProcessingError
from litres.extractors.audiobook import AudiobookExtractor
from litres.extractors.extras import find_extras
from litres.extractors.reader_pdf import ReaderPdfExtractor
from litres.extractors.reader_text import ReaderTextExtractor
from litres.handlers.book_handler import BookHandler
from litres.loaders.base_loader import BaseLoader
from litres.models.book import (
    AudioBook,
    Author,
    Book,
    BookFormat,
    BookMeta,
    BookRequest,
    ExtraFile,
)
from litres.models.book_paths import BookPaths
from litres.parsing import extra_files
from litres.services.litres_api import LitresApi

BONUS_URL = "https://www.litres.ru/download_book_subscr/50147324/136721046/bonus.pdf"

# Shaped like the real listings
LISTING = [
    {"id": 59097079, "filename": "00.mp3", "encoding_type": "standard_quality_mp3", "is_additional": False},
    {"id": 130885878, "filename": "book.mp3.zip", "encoding_type": "zip_with_mp3", "is_additional": False},
    {"id": 136721046, "filename": "bonus.pdf", "encoding_type": "additional_materials_mp3", "is_additional": True},
]


def meta():
    return BookMeta(authors=[Author(first="A")], title="T", version=1.0, uuid="u")


# --- model and parsing ---------------------------------------------------------------------


def test_books_have_no_extras_unless_given():
    assert Book(meta=meta(), parts=[]).extras == []
    assert Book(meta=meta(), parts=[]).extras is not Book(meta=meta(), parts=[]).extras


def test_extra_files_picks_only_additional_material_with_its_download_url():
    assert extra_files("50147324", LISTING) == [ExtraFile("bonus.pdf", BONUS_URL)]


def test_the_same_extra_listed_several_times_is_downloaded_once_from_its_newest_entry():
    files = [
        {"id": 10, "filename": "bonus.pdf", "is_additional": True, "release_date": "2026-01-01"},
        {"id": 30, "filename": "bonus.pdf", "is_additional": True, "release_date": "2026-03-01"},
        {"id": 20, "filename": "bonus.pdf", "is_additional": True, "release_date": "2026-02-01"},
    ]

    result = extra_files("1", files)

    assert [(e.filename, e.url.split("/")[-2]) for e in result] == [("bonus.pdf", "30")]


def test_ties_on_release_date_go_to_the_larger_id_and_missing_dates_lose():
    files = [
        {"id": 5, "filename": "a.zip", "is_additional": True, "release_date": None},
        {"id": 6, "filename": "a.zip", "is_additional": True, "release_date": "2026-05-17"},
        {"id": 8, "filename": "a.zip", "is_additional": True, "release_date": "2026-05-17"},
        {"id": 7, "filename": "a.zip", "is_additional": True, "release_date": "2026-05-17"},
    ]
    assert extra_files("1", files)[0].url.split("/")[-2] == "8"


def test_different_extra_files_are_all_kept_in_listing_order():
    files = [
        {"id": 1, "filename": "bonus.pdf", "is_additional": True},
        {"id": 2, "filename": "code.zip", "is_additional": True},
        {"id": 3, "filename": "bonus.pdf", "is_additional": True},
    ]
    assert [e.filename for e in extra_files("1", files)] == ["bonus.pdf", "code.zip"]


def test_extra_files_ignores_entries_without_a_file_name():
    files = [{"id": 1, "filename": "", "is_additional": True}, {"id": 2, "is_additional": True}]
    assert extra_files("1", files) == []


# --- extractors ---------------------------------------------------------------------------------


def api_with(files):
    api = MagicMock(spec=LitresApi)
    api.art.return_value = {"title": "T"}
    api.art_files.return_value = files
    return api


def test_audiobook_carries_its_extras():
    request = BookRequest(url="u", format=BookFormat.AUDIOBOOK, art_id="50147324")
    book = AudiobookExtractor(api_with(LISTING)).get(request)
    assert book.extras == [ExtraFile("bonus.pdf", BONUS_URL)]


def test_find_extras_without_an_art_id_makes_no_request():
    api = api_with(LISTING)
    assert find_extras(api, None) == []
    api.art_files.assert_not_called()


@pytest.mark.parametrize("error", [requests.ConnectionError("down"), BookProcessingError("bad body")])
def test_find_extras_swallows_failures_so_the_book_still_downloads(error, mocker):
    api = api_with([])
    api.art_files.side_effect = error
    warn = mocker.patch("litres.extractors.extras.logger.warning")

    assert find_extras(api, "1") == []
    warn.assert_called_once()


CONFIG = "x = {pages: [{rt: 'w640', p: [{w: 1, h: 2, ext: 'gif'}]}]};"
TOC = "{Meta: {Title: 'T'}, Parts: [{url: 'p.json'}]}"


def reader_api(body: str, files):
    api = api_with(files)
    api.file_link.return_value = "https://content/x"
    api.resource_link.return_value = "https://content/x"
    api.drm_params.return_value = {}
    api.download.return_value.content = body.encode()
    return api


def test_pdf_reader_book_carries_its_extras():
    files = [{"id": 7, "filename": "code.zip", "is_additional": True}]
    request = BookRequest(url="u", format=BookFormat.PDF_READER, file_id="5", art_id="73940202")

    book = ReaderPdfExtractor(reader_api(CONFIG, files)).get(request)

    assert [e.filename for e in book.extras] == ["code.zip"]
    assert book.resolution == "w640"  # the rest of the book is untouched


def test_text_reader_book_carries_its_extras():
    files = [{"id": 7, "filename": "notes.pdf", "is_additional": True}]
    request = BookRequest(url="u", format=BookFormat.TEXT_READER, file_id="5", art_id="1")

    book = ReaderTextExtractor(reader_api(TOC, files)).get(request)

    assert [e.filename for e in book.extras] == ["notes.pdf"]
    assert (book.file_id, book.art_id) == ("5", "1")


def test_a_failing_extras_lookup_does_not_stop_the_pdf_reader_book(mocker):
    mocker.patch("litres.extractors.extras.logger.warning")
    api = reader_api(CONFIG, [])
    api.art_files.side_effect = requests.ConnectionError("down")
    request = BookRequest(url="u", format=BookFormat.PDF_READER, file_id="5", art_id="1")

    book = ReaderPdfExtractor(api).get(request)

    assert book.extras == [] and book.total_parts == 1


# --- loader ------------------------------------------------------------------------------------------


class Loader(BaseLoader[AudioBook]):
    def _download_part(self, part_num, book, source_dir):
        return True


def audiobook(extras):
    return AudioBook(meta=meta(), art_id="50147324", parts=[], extras=extras)


def paths(tmp_path):
    paths = BookPaths("My Book", tmp_path / "src", tmp_path / "out")
    paths.makedirs()
    return paths


def response(body=b"%PDF", content_type="application/pdf"):
    resp = MagicMock()
    resp.headers = {"Content-Type": content_type}
    resp.iter_content.return_value = [body]
    return resp


def test_extras_are_saved_next_to_the_book_under_the_books_name(tmp_path):
    session = MagicMock()
    session.get.return_value = response(b"%PDF-bonus")
    book_paths = paths(tmp_path)

    Loader(session).download_extras(audiobook([ExtraFile("bonus.pdf", BONUS_URL)]), book_paths)

    assert session.get.call_args.args[0] == BONUS_URL
    assert (tmp_path / "out" / "My Book - bonus.pdf").read_bytes() == b"%PDF-bonus"


def test_existing_extras_are_not_downloaded_again(tmp_path):
    session = MagicMock()
    book_paths = paths(tmp_path)
    (tmp_path / "out" / "My Book - bonus.pdf").write_bytes(b"old")

    Loader(session).download_extras(audiobook([ExtraFile("bonus.pdf", BONUS_URL)]), book_paths)

    session.get.assert_not_called()
    assert (tmp_path / "out" / "My Book - bonus.pdf").read_bytes() == b"old"


def test_unsafe_characters_in_an_extra_name_are_replaced(tmp_path):
    session = MagicMock()
    session.get.return_value = response()

    Loader(session).download_extras(audiobook([ExtraFile("a:b?.pdf", BONUS_URL)]), paths(tmp_path))

    assert [p.name for p in (tmp_path / "out").iterdir()] == ["My Book - a_b_.pdf"]


def test_a_page_instead_of_the_file_is_not_saved_and_only_warns(tmp_path, mocker):
    warn = mocker.patch("litres.loaders.base_loader.logger.warning")
    session = MagicMock()
    html = response(b"<html>", "text/html; charset=utf-8")
    session.get.return_value = html

    Loader(session).download_extras(audiobook([ExtraFile("bonus.pdf", BONUS_URL)]), paths(tmp_path))

    assert list((tmp_path / "out").iterdir()) == []
    html.close.assert_called_once()
    warn.assert_called_once()


def test_one_failing_extra_does_not_stop_the_next(tmp_path, mocker):
    mocker.patch("litres.loaders.base_loader.logger.warning")
    session = MagicMock()
    session.get.side_effect = [requests.ConnectionError("down")] * 2 + [response(b"ok")]  # 2 attempts per file
    extras = [ExtraFile("bad.pdf", "https://x/bad"), ExtraFile("good.pdf", "https://x/good")]
    loader = Loader(session)
    mocker.patch.object(loader, "_rate_limiter")

    loader.download_extras(audiobook(extras), paths(tmp_path))

    assert [p.name for p in (tmp_path / "out").iterdir()] == ["My Book - good.pdf"]


# --- handler ------------------------------------------------------------------------------------------


def test_the_handler_downloads_extras_after_the_parts(tmp_path):
    calls = []
    extractor, loader = MagicMock(), MagicMock()
    extractor.get.return_value = audiobook([])
    loader.download_parts.side_effect = lambda *a: calls.append("parts")
    loader.download_extras.side_effect = lambda *a: calls.append("extras")
    handler = BookHandler(extractor, loader, [], tmp_path / "s", tmp_path / "b")

    handler.load(BookRequest(url="u", format=BookFormat.AUDIOBOOK, art_id="1"))

    assert calls == ["parts", "extras"]
    book, book_paths = loader.download_extras.call_args.args
    assert book is extractor.get.return_value
    assert book_paths.output == tmp_path / "b"
