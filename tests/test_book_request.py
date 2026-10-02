from unittest.mock import MagicMock

import pytest
import requests

from litres.book_request import BookRequestResolver
from litres.exceptions import BookProcessingError
from litres.models.book import BookFormat
from litres.services.litres_api import LitresApi

PAGE = "https://www.litres.ru/book/arseniy-kravchenko/mashinnoe-obuchenie-ot-idei-do-re-73940202/"

# Shaped like GET /api/arts/{id}/files for a PDF book (extensions are all null)
PDF_BOOK_FILES = [
    {"id": 134358857, "extension": None, "encoding_type": "pdf_book", "is_additional": False},
    {"id": 134358862, "extension": None, "encoding_type": "introductory_fragment_pdf", "is_additional": False},
    {"id": 134358867, "extension": None, "encoding_type": "additional_materials_pdf", "is_additional": True},
]

# ...and for a text book: old versions without extensions, the current file once per format
TEXT_BOOK_FILES = [
    {"id": 137241719, "extension": None, "encoding_type": "unknown"},
    {"id": 140796813, "extension": "fb2.zip", "encoding_type": "unknown"},
    {"id": 140796813, "extension": "txt", "encoding_type": "unknown"},
    {"id": 140796813, "extension": "a4.pdf", "encoding_type": "unknown"},
    {"id": 140796813, "extension": "fb3", "encoding_type": "unknown"},
]


def make_resolver(files=None, error=None):
    api = MagicMock(spec=LitresApi)
    if error:
        api.art_files.side_effect = error
    else:
        api.art_files.return_value = files or []
    session = MagicMock()
    return BookRequestResolver(session, api), api, session


# --- book pages ---------------------------------------------------------------------


def test_a_pdf_book_page_resolves_to_the_pdf_reader():
    resolver, api, session = make_resolver(PDF_BOOK_FILES)

    bq = resolver.resolve(PAGE)

    assert bq.format is BookFormat.PDF_READER
    assert (bq.file_id, bq.art_id, bq.url) == ("134358857", "73940202", PAGE)
    api.art_files.assert_called_once_with("73940202")
    session.get.assert_not_called()  # no HTML scraping


def test_a_text_book_page_resolves_to_the_text_reader_even_with_a_pdf_present():
    resolver, _, _ = make_resolver(TEXT_BOOK_FILES)

    bq = resolver.resolve("https://www.litres.ru/book/m-vestchester/poslednee-74208177/")

    assert bq.format is BookFormat.TEXT_READER
    assert (bq.file_id, bq.art_id) == ("140796813", "74208177")


def test_the_pdf_fragment_and_extra_materials_are_never_chosen():
    only_extras = PDF_BOOK_FILES[1:]
    resolver, _, _ = make_resolver(only_extras)
    with pytest.raises(BookProcessingError, match="No readable"):
        resolver.resolve(PAGE)


def test_pdf_extension_files_are_found_without_an_encoding_type():
    files = [{"id": 5, "extension": "a4.pdf", "encoding_type": "unknown"}]
    resolver, _, _ = make_resolver(files)
    bq = resolver.resolve(PAGE)
    assert (bq.format, bq.file_id) == (BookFormat.PDF_READER, "5")


def test_a_page_url_with_a_trailing_slash_missing_still_gives_the_art_id():
    resolver, api, _ = make_resolver(PDF_BOOK_FILES)
    resolver.resolve(PAGE.rstrip("/"))
    api.art_files.assert_called_once_with("73940202")


@pytest.mark.parametrize("files", [[], [{"id": 1, "extension": "mp3", "encoding_type": "x"}]])
def test_a_page_without_a_readable_file_is_an_error(files):
    resolver, _, _ = make_resolver(files)
    with pytest.raises(BookProcessingError, match="No readable"):
        resolver.resolve(PAGE)


def test_api_failures_become_book_processing_errors():
    resolver, _, _ = make_resolver(error=requests.ConnectionError("down"))
    with pytest.raises(BookProcessingError, match="Could not list files for art 73940202"):
        resolver.resolve(PAGE)


# --- direct URLs (no network) ------------------------------------------------------


@pytest.mark.parametrize(
    "url,fmt,file_id,base_url,art_id",
    [
        (
            "https://www.litres.ru/static/or3/view/or.html?art_type=1&file=999&user=5",
            BookFormat.O3,
            "999",
            None,
            None,
        ),
        (
            "https://www.litres.ru/static/or4/view/or.html?baseurl=/download_book_subscr/1/2/&art=1",
            BookFormat.O4,
            None,
            "/download_book_subscr/1/2/",
            None,
        ),
        (
            "https://www.litres.ru/static/reader/pdf/index.html?file=39305103&art=25030016&user=1",
            BookFormat.PDF_READER,
            "39305103",
            None,
            "25030016",
        ),
        (
            "https://www.litres.ru/audiobook/some-author/some-book-123/",
            BookFormat.AUDIOBOOK,
            None,
            None,
            "123",
        ),
    ],
)
def test_create_from_direct_url(url, fmt, file_id, base_url, art_id):
    resolver, api, session = make_resolver()

    bq = resolver.resolve(url)

    assert (bq.format, bq.file_id, bq.base_url, bq.art_id, bq.url) == (
        fmt,
        file_id,
        base_url,
        art_id,
        url,
    )
    session.get.assert_not_called()
    api.art_files.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "https://www.litres.ru/static/or3/view/or.html",  # no file id
        "https://www.litres.ru/static/or4/view/or.html?art=1",  # no baseurl
        "https://www.litres.ru/static/reader/pdf/index.html?art=1&user=2",  # no file
        "https://www.litres.ru/audiobook/no-art-id-in-this-one/",
        "https://other.ru/foo/123/",
        "not a url",
    ],
)
def test_create_from_unsupported_url_raises(url):
    resolver, _, _ = make_resolver()
    with pytest.raises(BookProcessingError, match="Unsupported URL format"):
        resolver.resolve(url)
