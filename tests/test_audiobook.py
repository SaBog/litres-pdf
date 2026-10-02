from unittest.mock import MagicMock

import pytest
import requests

from litres.book_request import BookRequestResolver
from litres.exceptions import BookProcessingError
from litres.extractors.audiobook import AudiobookExtractor
from litres.loaders.audio_loader import AudioLoader
from litres.models.book import (
    AudioBook,
    Author,
    BookFormat,
    BookMeta,
    BookRequest,
)
from litres.services.litres_api import API_BASE, LitresApi
from litres.utils import natural_key, natural_sorted

PAGE = "https://www.litres.ru/audiobook/dzheyms-klir/atomnye-privychki-50147324/"


def mp3(file_id, name, encoding="standard_quality_mp3", additional=False):
    return {
        "id": file_id,
        "filename": name,
        "encoding_type": encoding,
        "is_additional": additional,
    }


# Shaped like the real listing: parts out of order, plus a sample, a zip, an m4b and a bonus
FILES = [
    mp3(59096959, "09.mp3"),
    mp3(59096983, "04.mp3"),
    mp3(59097007, "sample.mp3", "introductory_fragment_mp3"),
    mp3(59097079, "00.mp3"),
    mp3(59097055, "02.mp3"),
    mp3(59097487, "10.mp3"),
    mp3(130885878, "book.mp3.zip", "zip_with_mp3"),
    mp3(130886128, "book.m4b", "mobile_version_mp4"),
    mp3(136721046, "bonus.pdf", "additional_materials_mp3", additional=True),
]


def make_api(files=None, art=None):
    api = MagicMock(spec=LitresApi)
    api.art.return_value = (
        art if art is not None else {"title": "Атомные привычки", "uuid": "u-1"}
    )
    api.art_files.return_value = FILES if files is None else files
    return api


def request(art_id="50147324"):
    return BookRequest(url=PAGE, format=BookFormat.AUDIOBOOK, art_id=art_id)


# --- resolving the page ----------------------------------------------------------------


def test_the_audiobook_page_carries_the_art_id_and_needs_no_network():
    session = MagicMock()
    api = MagicMock(spec=LitresApi)

    bq = BookRequestResolver(session, api).resolve(PAGE)

    assert bq.format is BookFormat.AUDIOBOOK
    assert bq.art_id == "50147324"
    session.get.assert_not_called()
    api.art_files.assert_not_called()


# --- extractor ---------------------------------------------------------------------------


def test_parts_are_the_standard_quality_mp3s_in_listening_order():
    book = AudiobookExtractor(make_api()).get(request())

    assert [p["filename"] for p in book.parts] == [
        "00.mp3",
        "02.mp3",
        "04.mp3",
        "09.mp3",
        "10.mp3",
    ]
    assert [p["file_id"] for p in book.parts][:2] == ["59097079", "59097055"]


def test_part_urls_use_the_download_path():
    book = AudiobookExtractor(make_api()).get(request())

    assert book.parts[0]["url"] == (
        "https://www.litres.ru/download_book_subscr/50147324/59097079/00.mp3"
    )


def test_sample_zip_m4b_and_bonus_files_are_not_parts():
    names = [p["filename"] for p in AudiobookExtractor(make_api()).get(request()).parts]
    assert not {"sample.mp3", "book.mp3.zip", "book.m4b", "bonus.pdf"} & set(names)


def test_additional_materials_that_are_mp3_are_skipped():
    files = [mp3(1, "00.mp3"), mp3(2, "extra.mp3", additional=True)]
    book = AudiobookExtractor(make_api(files)).get(request())
    assert [p["filename"] for p in book.parts] == ["00.mp3"]


def test_meta_has_the_title_and_the_art_uuid():
    book = AudiobookExtractor(make_api()).get(request())

    assert book.meta.title == "Аудиокнига Атомные привычки"
    assert book.meta.uuid == "u-1"
    assert book.art_id == "50147324"


def test_meta_without_a_title_is_not_duplicated():
    api = make_api(art={})
    assert AudiobookExtractor(api).get(request()).meta.title == "Аудиокнига"


def test_extractor_asks_the_api_for_this_art():
    api = make_api()
    AudiobookExtractor(api).get(request())
    api.art.assert_called_once_with("50147324")
    api.art_files.assert_called_once_with("50147324")


def test_extractor_requires_an_art_id():
    api = make_api()
    with pytest.raises(BookProcessingError, match="art id"):
        AudiobookExtractor(api).get(request(art_id=None))
    api.art_files.assert_not_called()


def test_an_art_without_audio_parts_is_an_error():
    api = make_api(files=[mp3(1, "sample.mp3", "introductory_fragment_mp3")])
    with pytest.raises(BookProcessingError, match="No audio parts"):
        AudiobookExtractor(api).get(request())


def test_network_errors_become_book_processing_errors():
    api = make_api()
    api.art_files.side_effect = requests.ConnectionError("down")
    with pytest.raises(BookProcessingError, match="Audiobook metadata retrieval error"):
        AudiobookExtractor(api).get(request())


# --- API client ----------------------------------------------------------------------------


def test_art_returns_the_data_object():
    session = MagicMock()
    session.cookies.get.return_value = None
    session.get.return_value.json.return_value = {"payload": {"data": {"title": "T"}}}

    assert LitresApi(session, MagicMock()).art("1") == {"title": "T"}
    assert session.get.call_args.args[0] == f"{API_BASE}/arts/1"


def test_art_rejects_unexpected_bodies():
    session = MagicMock()
    session.cookies.get.return_value = None
    session.get.return_value.json.return_value = {"payload": {"data": []}}
    with pytest.raises(BookProcessingError, match="Unexpected art response"):
        LitresApi(session, MagicMock()).art("1")


# --- loader ----------------------------------------------------------------------------------


def make_book():
    meta = BookMeta(authors=[Author(first="A")], title="T", version=1.0, uuid="u")
    parts = AudiobookExtractor._parts("50147324", [mp3(59097079, "00.mp3"), mp3(59097055, "02.mp3")])
    return AudioBook(meta=meta, art_id="50147324", parts=parts)


def make_loader(content_type="audio/mpeg", body=b"ID3data"):
    session = MagicMock()
    response = MagicMock()
    response.headers = {"Content-Type": content_type}
    response.iter_content.return_value = [body]
    session.get.return_value = response
    return AudioLoader(session), session, response


def test_loader_downloads_a_part_from_the_download_path(tmp_path):
    loader, session, _ = make_loader()

    assert loader._download_part(1, make_book(), tmp_path) is True

    assert session.get.call_args.args[0] == (
        "https://www.litres.ru/download_book_subscr/50147324/59097055/02.mp3"
    )
    assert (tmp_path / "1.mp3").read_bytes() == b"ID3data"


def test_loader_rejects_an_html_answer_instead_of_saving_it_as_audio(tmp_path, mocker):
    error = mocker.patch("litres.loaders.audio_loader.logger.error")
    loader, _, response = make_loader(content_type="text/html; charset=utf-8", body=b"<html>")

    assert loader._download_part(0, make_book(), tmp_path) is False

    assert not (tmp_path / "0.mp3").exists()
    response.close.assert_called_once()
    error.assert_called_once()


# --- ordering helpers -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "names,expected",
    [
        (["10.mp3", "2.mp3", "01.mp3", "00.mp3"], ["00.mp3", "01.mp3", "2.mp3", "10.mp3"]),
        (["b.mp3", "10.mp3", "a.mp3"], ["10.mp3", "a.mp3", "b.mp3"]),
    ],
)
def test_natural_key_orders_numbered_names_by_value(names, expected):
    assert sorted(names, key=natural_key) == expected


def test_natural_sorted_still_sorts_paths(tmp_path):
    paths = [tmp_path / "10.mp3", tmp_path / "2.mp3"]
    assert [p.name for p in natural_sorted(paths)] == ["2.mp3", "10.mp3"]
