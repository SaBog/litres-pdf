import json
from unittest.mock import MagicMock

import pytest

from litres.book_request import BookRequestResolver
from litres.engines.o3.pdf_engine import IMG2PDFEngine
from litres.exceptions import BookProcessingError
from litres.models.book import BookFormat
from litres.services.cookie_store import CookieStore

READER_URL = (
    "https://www.litres.ru/static/reader/pdf/index.html?file=39305103"
    "&title=%D0%9C%D0%BE%D0%B4%D0%BD%D1%8B%D0%B5%20%D0%BF%D0%BB%D0%B0%D1%82%D1%8C%D1%8F"
    "%20%26%20%D0%A1%D1%82%D0%B8%D0%BB%D1%8C%D0%BD%D1%8B%D0%B5"
    "&art=25030016&user=1256995562&uilang=ru"
)


def test_reader_url_is_recognised_without_network():
    session = MagicMock()
    bq = BookRequestResolver(session).resolve(READER_URL)

    assert bq.format is BookFormat.PDF_READER
    assert bq.file_id == "39305103"
    assert bq.art_id == "25030016"
    assert bq.url == READER_URL
    session.get.assert_not_called()


def test_reader_url_without_art_still_resolves():
    bq = BookRequestResolver(MagicMock()).resolve(
        "https://www.litres.ru/static/reader/pdf/index.html?file=1&user=2"
    )
    assert (bq.format, bq.file_id, bq.art_id) == (BookFormat.PDF_READER, "1", None)


def test_reader_url_without_file_is_unsupported():
    with pytest.raises(BookProcessingError, match="Unsupported URL format"):
        BookRequestResolver(MagicMock()).resolve(
            "https://www.litres.ru/static/reader/pdf/index.html?art=1&user=2"
        )


def test_old_or3_url_still_resolves_to_the_old_format():
    bq = BookRequestResolver(MagicMock()).resolve(
        "https://www.litres.ru/static/or3/view/or.html?art_type=1&file=999&user=5"
    )
    assert (bq.format, bq.file_id) == (BookFormat.O3, "999")


@pytest.mark.parametrize(
    "names,expected",
    [
        (["1.gif", "0.jpg", "2.png", "3.jpeg"], ["0.jpg", "1.gif", "2.png", "3.jpeg"]),
        (["0.GIF", "1.JPG"], ["0.GIF", "1.JPG"]),
        (["0.gif", "0.gif.12.34.part", "notes.txt", "1.pdf"], ["0.gif"]),
    ],
)
def test_engine_collects_every_supported_image_type(tmp_path, names, expected):
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    engine = IMG2PDFEngine()
    assert sorted(p.name for p in engine._get_images(tmp_path)) == sorted(expected)


def test_cookie_store_keeps_supersid_next_to_sid(tmp_path):
    path = tmp_path / "cookies.json"
    store = CookieStore(path)

    saved = store.save(
        [
            {"name": "OTHER", "value": "x"},
            {"name": "SID", "value": "1"},
            {"name": "supersid", "value": "2"},
        ]
    )

    assert saved is True
    assert [c["name"] for c in json.loads(path.read_text(encoding="utf-8"))] == [
        "SID",
        "supersid",
    ]


def test_cookie_store_needs_sid_even_if_supersid_is_present(tmp_path):
    store = CookieStore(tmp_path / "cookies.json")
    assert store.save([{"name": "supersid", "value": "2"}]) is False
