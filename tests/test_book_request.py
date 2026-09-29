import json
from unittest.mock import MagicMock

import pytest

from litres.book_request import BookRequestResolver
from litres.exceptions import BookProcessingError
from litres.models.book import BookFormat


def make_command(session=None) -> BookRequestResolver:
    return BookRequestResolver(session or MagicMock())


def page_html(state: dict) -> str:
    """Build a page with the Next.js initialState blob the command parses."""
    escaped = json.dumps(json.dumps(state))[1:-1]
    return f'..."initialState":"{escaped}"' + '},"__N_SSP"...'


def book_page_session(state: dict) -> MagicMock:
    session = MagicMock()
    session.get.return_value.text = page_html(state)
    return session


def state_with(files: list[dict], art_id: int | None = 77) -> dict:
    queries: dict = {"getArtFiles({})": {"data": files}}
    if art_id is not None:
        queries["getArtData({})"] = {"data": {"id": art_id}}
    return {"rtkqApi": {"queries": queries}}


# _extract_art_data_and_files
@pytest.mark.parametrize(
    "state,expected_art,expected_files",
    [
        (
            {
                "rtkqApi": {
                    "queries": {
                        "getArtData(1)": {"data": {"id": 1, "art_type": "book"}},
                        "getArtFiles(1)": {"data": [{"id": "f1", "extension": "pdf"}]},
                    }
                }
            },
            {"id": 1, "art_type": "book"},
            [{"id": "f1", "extension": "pdf"}],
        ),
        ({"rtkqApi": {"queries": {}}}, None, None),
    ],
)
def test_extract_art_data_and_files(state, expected_art, expected_files):
    art, files = make_command()._extract_art_data_and_files(state)
    assert art == expected_art
    assert files == expected_files


# _detect_book_format_and_file
@pytest.mark.parametrize(
    "art_files,expected_format,expected_file_id",
    [
        ([{"id": "f1", "extension": "txt"}], BookFormat.O4, "f1"),
        ([{"id": "f2", "extension": "pdf"}], BookFormat.O3, "f2"),
        (
            [{"id": "f4", "filename": "b.pdf", "encoding_type": "pdf_book"}],
            BookFormat.O3,
            "f4",
        ),
        ([{"id": "f3", "extension": "unknown"}], None, None),
        ([], None, None),
        (None, None, None),
    ],
)
def test_detect_book_format_and_file(art_files, expected_format, expected_file_id):
    fmt, file_id = make_command()._detect_book_format_and_file(art_files)
    assert fmt == expected_format
    assert file_id == expected_file_id


# create: book pages
def test_create_from_book_page_o4():
    session = book_page_session(state_with([{"id": "f1", "extension": "txt"}]))
    bq = make_command(session).resolve("https://www.litres.ru/book/author/title-123/")

    assert bq.format is BookFormat.O4
    assert bq.file_id == "f1"
    assert bq.art_id == 77
    assert bq.base_url == "/download_book_subscr/77/f1/"
    assert bq.url == "https://www.litres.ru/book/author/title-123/"


def test_create_from_book_page_o3():
    session = book_page_session(state_with([{"id": "f2", "extension": "a4.pdf"}]))
    bq = make_command(session).resolve("https://www.litres.ru/book/a/t-1")

    assert bq.format is BookFormat.O3
    assert bq.file_id == "f2"


@pytest.mark.parametrize(
    "state",
    [
        state_with([{"id": "f", "extension": "epub"}]),  # no supported file
        state_with([{"id": "f", "extension": "txt"}], art_id=None),  # no art data
        state_with([]),
    ],
)
def test_create_from_book_page_without_usable_file_raises(state):
    session = book_page_session(state)
    with pytest.raises(BookProcessingError, match="Could not determine"):
        make_command(session).resolve("https://www.litres.ru/book/a/t-1/")


def test_create_initial_state_error():
    session = MagicMock()
    session.get.return_value.text = "no initialState here"
    with pytest.raises(ValueError):
        make_command(session).resolve("https://www.litres.ru/book/a/t-1/")


# create: direct URLs (no network)
@pytest.mark.parametrize(
    "url,fmt,file_id,base_url",
    [
        (
            "https://www.litres.ru/static/or3/view/or.html?art_type=1&file=999&user=5",
            BookFormat.O3,
            "999",
            None,
        ),
        (
            "https://www.litres.ru/static/or4/view/or.html?baseurl=/download_book_subscr/1/2/&art=1",
            BookFormat.O4,
            None,
            "/download_book_subscr/1/2/",
        ),
        (
            "https://www.litres.ru/audiobook/some-author/some-book-123/",
            BookFormat.AUDIOBOOK,
            None,
            None,
        ),
    ],
)
def test_create_from_direct_url(url, fmt, file_id, base_url):
    session = MagicMock()
    bq = make_command(session).resolve(url)

    assert (bq.format, bq.file_id, bq.base_url, bq.url) == (fmt, file_id, base_url, url)
    session.get.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "https://www.litres.ru/static/or3/view/or.html",  # no file id
        "https://www.litres.ru/static/or4/view/or.html?art=1",  # no baseurl
        "https://other.ru/book/123/",
        "not a url",
    ],
)
def test_create_from_unsupported_url_raises(url):
    with pytest.raises(BookProcessingError, match="Unsupported URL format"):
        make_command().resolve(url)
