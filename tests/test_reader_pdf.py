from unittest.mock import MagicMock

import pytest
import requests

from litres.exceptions import BookProcessingError
from litres.extractors.reader_pdf import ReaderPdfExtractor
from litres.loaders.reader_loader import MAX_ATTEMPTS
from litres.loaders.reader_page_loader import ReaderPageLoader
from litres.models.book import (
    Author,
    BookFormat,
    BookMeta,
    BookRequest,
    Page,
    PdfBook,
)
from litres.services.litres_api import LitresApi

CONFIG = """
window.litres_pdf_config[39305103] = {
  Meta: {Title: 'Модные платья', UUID: 'uu-1', version: 3,
         Authors: [{First: 'Галина', Last: 'Злачевская'}]},
  pages: [
    {rt: 'w640', w: 640, p: [{w: 640, h: 905, ext: 'gif'}, {w: 640, h: 905, ext: 'gif'}]},
    {rt: 'w1900', w: 1900, p: [{w: 1900, h: 2687, ext: 'gif'}, {w: 1900, h: 2687, ext: 'jpg'}]},
    {rt: 'w1280', w: 1280, p: [{w: 1280, h: 1810, ext: 'gif'}]},
  ]
};
"""


def make_api_for_config(text=CONFIG, drm=None):
    api = MagicMock(spec=LitresApi)
    api.drm_params.return_value = drm or {}
    api.file_link.return_value = "https://content.litres.ru/config"
    api.download.return_value.content = text.encode("utf-8")
    return api


def request(file_id: str | None = "39305103", art_id: str | None = "25030016"):
    return BookRequest(
        url="u", format=BookFormat.PDF_READER, file_id=file_id, art_id=art_id
    )


# --- extractor ---------------------------------------------------------------


def test_extractor_asks_for_the_config_link_with_drm_params():
    api = make_api_for_config(drm={"timestamp": "5", "md5": "m"})

    ReaderPdfExtractor(api).get(request())

    api.drm_params.assert_called_once_with("25030016")
    api.file_link.assert_called_once_with(
        "39305103", index=1, is_trial="false", timestamp="5", md5="m"
    )
    api.download.assert_called_once_with("https://content.litres.ru/config")


def test_extractor_picks_the_sharpest_page_variant():
    book = ReaderPdfExtractor(make_api_for_config()).get(request())

    assert book.resolution == "w1900"
    assert [(p.width, p.height, p.extension) for p in book.parts] == [
        (1900, 2687, "gif"),
        (1900, 2687, "jpg"),
    ]


def test_extractor_reads_meta_and_ids():
    book = ReaderPdfExtractor(make_api_for_config()).get(request())

    assert (book.file_id, book.art_id) == ("39305103", "25030016")
    assert book.meta.title == "Модные платья"
    assert book.meta.uuid == "uu-1"
    assert [str(a) for a in book.meta.authors] == ["Галина Злачевская"]


def test_extractor_defaults_resolution_when_variant_has_none():
    text = "x = {pages: [{p: [{w: 100, h: 200, ext: 'gif'}]}]};"
    book = ReaderPdfExtractor(make_api_for_config(text)).get(request())
    assert book.resolution == "w640"
    assert book.meta.title == "Unknown_39305103"


@pytest.mark.parametrize(
    "text",
    ["no assignment here", "x = {not json at all", "x = {pages: []};", "x = {};"],
)
def test_extractor_rejects_unusable_configs(text):
    with pytest.raises(BookProcessingError):
        ReaderPdfExtractor(make_api_for_config(text)).get(request())


def test_extractor_decodes_utf8_even_if_requests_guessed_latin1():
    api = make_api_for_config()
    response = api.download.return_value
    # what requests.text yields when the server sends no charset
    response.text = CONFIG.encode("utf-8").decode("latin-1")

    book = ReaderPdfExtractor(api).get(request())

    assert book.meta.title == "Модные платья"
    assert [str(a) for a in book.meta.authors] == ["Галина Злачевская"]


def test_extractor_rejects_a_config_that_is_not_utf8():
    api = make_api_for_config()
    api.download.return_value.content = CONFIG.encode("cp1251")
    with pytest.raises(BookProcessingError, match="UTF-8"):
        ReaderPdfExtractor(api).get(request())


def test_extractor_requires_file_id():
    api = make_api_for_config()
    with pytest.raises(BookProcessingError, match="file_id"):
        ReaderPdfExtractor(api).get(request(file_id=None))
    api.file_link.assert_not_called()


def test_extractor_wraps_network_errors():
    api = make_api_for_config()
    api.file_link.side_effect = requests.ConnectionError("down")
    with pytest.raises(BookProcessingError, match="Reader config retrieval error"):
        ReaderPdfExtractor(api).get(request())


# --- loader ------------------------------------------------------------------


def make_book(extension="gif", resolution="w1900") -> PdfBook:
    meta = BookMeta(authors=[Author(first="A")], title="T", version=1.0, uuid="u")
    return PdfBook(
        meta=meta,
        parts=[Page(1900, 2687, extension), Page(1900, 2687, extension)],
        file_id="39305103",
        art_id="25030016",
        resolution=resolution,
    )


def make_loader(api=None):
    api = api or MagicMock(spec=LitresApi)
    api.session = MagicMock()
    api.drm_params.return_value = {}
    api.file_link.return_value = "https://content.litres.ru/p"
    image = MagicMock()
    image.iter_content.return_value = [b"GIF89a", b"data"]
    api.download.return_value = image
    return ReaderPageLoader(api), api, image


def test_loader_requests_the_page_link_then_saves_the_image(tmp_path):
    loader, api, image = make_loader()

    assert loader._download_part(1, make_book(), tmp_path) is True

    api.file_link.assert_called_once_with(
        "39305103",
        page_id=1,
        is_trial="false",
        resolution="w1900",
        image_type="gif",
    )
    api.download.assert_called_once_with("https://content.litres.ru/p")
    assert (tmp_path / "1.gif").read_bytes() == b"GIF89adata"
    image.close.assert_called_once()


def test_loader_adds_drm_params_to_the_page_link(tmp_path):
    loader, api, _ = make_loader()
    api.drm_params.return_value = {"timestamp": "5", "md5": "m"}

    loader._download_part(0, make_book(), tmp_path)

    kwargs = api.file_link.call_args.kwargs
    assert (kwargs["timestamp"], kwargs["md5"]) == ("5", "m")


def test_loader_names_files_after_the_page_extension(tmp_path):
    loader, _, _ = make_loader()
    loader._download_part(0, make_book(extension="png"), tmp_path)
    assert (tmp_path / "0.png").exists()


def test_loader_retries_with_a_fresh_link_and_signature(tmp_path, mocker):
    sleep = mocker.patch("litres.loaders.reader_loader.time.sleep")
    loader, api, _ = make_loader()
    api.file_link.side_effect = [
        requests.HTTPError("403 expired"),
        "https://content.litres.ru/fresh",
    ]

    assert loader._download_part(0, make_book(), tmp_path) is True

    assert api.file_link.call_count == 2
    api.reset_drm.assert_called_once()
    api.download.assert_called_once_with("https://content.litres.ru/fresh")
    sleep.assert_called_once()


def test_loader_gives_up_after_max_attempts(tmp_path, mocker):
    mocker.patch("litres.loaders.reader_loader.time.sleep")
    error = mocker.patch("litres.loaders.reader_page_loader.logger.error")
    loader, api, _ = make_loader()
    api.download.side_effect = requests.ConnectionError("down")

    assert loader._download_part(0, make_book(), tmp_path) is False

    assert api.download.call_count == MAX_ATTEMPTS
    error.assert_called_once()
    assert list(tmp_path.iterdir()) == []


def test_loader_429_pauses_every_worker(tmp_path, mocker):
    mocker.patch("litres.loaders.reader_loader.time.sleep")
    loader, api, _ = make_loader()
    too_many = MagicMock(status_code=429, headers={"Retry-After": "7"})
    api.file_link.side_effect = [
        requests.HTTPError(response=too_many),
        "https://content.litres.ru/p",
    ]
    penalize = mocker.patch.object(loader._rate_limiter, "penalize")

    assert loader._download_part(0, make_book(), tmp_path) is True
    penalize.assert_called_once_with(7.0)


def test_loader_unexpected_link_response_counts_as_a_failed_attempt(tmp_path, mocker):
    mocker.patch("litres.loaders.reader_loader.time.sleep")
    loader, api, _ = make_loader()
    api.file_link.side_effect = BookProcessingError("bad body")
    assert loader._download_part(0, make_book(), tmp_path) is False
    assert api.file_link.call_count == MAX_ATTEMPTS


def test_loader_falls_back_to_default_resolution(tmp_path):
    loader, api, _ = make_loader()
    book = make_book(resolution="w1900")
    book.resolution = None
    loader._download_part(0, book, tmp_path)
    assert api.file_link.call_args.kwargs["resolution"] == "w640"
