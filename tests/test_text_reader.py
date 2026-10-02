from unittest.mock import MagicMock

import pytest
import requests

from litres.book_request import BookRequestResolver
from litres.exceptions import BookProcessingError
from litres.extractors.reader_text import ReaderTextExtractor
from litres.loaders.reader_loader import MAX_ATTEMPTS
from litres.loaders.reader_text_loader import ReaderTextLoader
from litres.models.book import Author, BookFormat, BookMeta, BookRequest, TextBook
from litres.models.book_paths import BookPaths
from litres.parsing import image_names
from litres.services.litres_api import API_BASE, LitresApi

BASE = "https://www.litres.ru/static/reader/text/index.html"

# Shaped like GET /api/arts/{id}/files: many old versions without extensions,
# and the current file repeated once per available format.
FILES = [
    {"id": 137241719, "extension": None},
    {"id": 140661207, "extension": None},
    {"id": 140796813, "extension": "fb2.zip"},
    {"id": 140796813, "extension": "txt"},
    {"id": 140796813, "extension": "fb3"},
]

TOC = """{
  Meta: {Title: 'Последнее па-де-де в темноте', UUID: 'u-1', version: 2,
         Authors: [{First: 'Мэри', Last: 'Вестчестер'}],},
  Parts: [{url: 'part_0.json', s: 1}, {url: 'Part_1.json', s: 2},],
}"""


def make_api():
    api = MagicMock(spec=LitresApi)
    api.session = MagicMock()
    return api


# --- URL resolution ----------------------------------------------------------


def test_art_only_url_finds_the_current_file_through_the_api():
    api = make_api()
    api.art_files.return_value = FILES

    bq = BookRequestResolver(MagicMock(), api).resolve(f"{BASE}?art=74208177")

    assert bq.format is BookFormat.TEXT_READER
    assert (bq.file_id, bq.art_id) == ("140796813", "74208177")
    api.art_files.assert_called_once_with("74208177")


def test_file_param_skips_the_api():
    api = make_api()
    bq = BookRequestResolver(MagicMock(), api).resolve(f"{BASE}?art=1&file=555&user=2")

    assert (bq.file_id, bq.art_id) == ("555", "1")
    api.art_files.assert_not_called()


@pytest.mark.parametrize(
    "baseurl,expected",
    [
        ("/download_book_subscr/74208177/140796813/", "140796813"),
        ("/download_book_subscr/74208177/140796813", "140796813"),
        ("/download_book_subscr/74208177/140796813/.", "140796813"),
    ],
)
def test_baseurl_param_carries_the_file_id(baseurl, expected):
    api = make_api()
    url = f"{BASE}?art=74208177&baseurl={baseurl}"

    bq = BookRequestResolver(MagicMock(), api).resolve(url)

    assert bq.file_id == expected
    api.art_files.assert_not_called()


def test_file_extension_preference_is_fb3_then_txt():
    api = make_api()
    api.art_files.return_value = [
        {"id": 2, "extension": "txt"},
        {"id": 3, "extension": "fb3"},
    ]
    bq = BookRequestResolver(MagicMock(), api).resolve(f"{BASE}?art=1")
    assert bq.file_id == "3"


def test_art_without_a_readable_file_is_an_error():
    api = make_api()
    api.art_files.return_value = [{"id": 1, "extension": None}, {"id": 2, "extension": "mp3"}]
    with pytest.raises(BookProcessingError, match="No readable text file"):
        BookRequestResolver(MagicMock(), api).resolve(f"{BASE}?art=1")


def test_trial_links_are_rejected_clearly():
    with pytest.raises(BookProcessingError, match="Trial"):
        BookRequestResolver(MagicMock(), make_api()).resolve(f"{BASE}?art=1&trials=1")


def test_text_reader_url_without_art_is_unsupported():
    with pytest.raises(BookProcessingError, match="Unsupported URL format"):
        BookRequestResolver(MagicMock(), make_api()).resolve(f"{BASE}?file=1")


# --- LitresApi additions -------------------------------------------------------


def response(body=None, status=200, headers=None):
    resp = MagicMock(status_code=status)
    resp.json.return_value = body
    resp.headers = headers or {}
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def make_real_api(*responses):
    session = MagicMock()
    session.cookies.get.return_value = None
    session.get.side_effect = list(responses)
    return LitresApi(session, MagicMock()), session


def link_body(link="https://content/x"):
    return {"status": 200, "payload": {"data": {"link": link}}}


def test_resource_link_lowercases_the_resource_and_skips_drm_at_first():
    api, session = make_real_api(response(link_body("https://content/toc")))

    link = api.resource_link("140796813", "TOC.JS", art_id="74208177")

    assert link == "https://content/toc"
    assert session.get.call_count == 1  # no DRM request
    assert session.get.call_args.args[0] == f"{API_BASE}/arts/files/140796813/link"
    assert session.get.call_args.kwargs["params"] == {
        "resource": "toc.js",
        "is_trial": "false",
    }


def test_resource_link_retries_with_a_drm_signature_after_422():
    api, session = make_real_api(
        response(status=422),  # first link request
        response(headers={"Drm3-Key": "1790965451:abc"}),  # arts/{id}
        response(link_body("https://content/signed")),
    )

    link = api.resource_link("1", "toc.js", art_id="9")

    assert link == "https://content/signed"
    last_params = session.get.call_args.kwargs["params"]
    assert (last_params["timestamp"], last_params["md5"]) == ("1790965451", "abc")


def test_resource_link_422_without_a_signature_is_still_an_error():
    api, _ = make_real_api(response(status=422), response())  # no Drm3-Key header
    with pytest.raises(requests.HTTPError):
        api.resource_link("1", "toc.js", art_id="9")


def test_resource_link_other_errors_are_not_retried():
    api, session = make_real_api(response(status=403))
    with pytest.raises(requests.HTTPError):
        api.resource_link("1", "toc.js", art_id="9")
    assert session.get.call_count == 1


def test_art_files_returns_the_listing():
    api, session = make_real_api(response({"payload": {"data": FILES}}))
    assert api.art_files("74208177") == FILES
    assert session.get.call_args.args[0] == f"{API_BASE}/arts/74208177/files"


def test_art_files_rejects_unexpected_bodies():
    api, _ = make_real_api(response({"payload": {"data": {"not": "a list"}}}))
    with pytest.raises(BookProcessingError, match="Unexpected files response"):
        api.art_files("1")


# --- extractor -------------------------------------------------------------------


def make_toc_api(toc=TOC):
    api = make_api()
    api.resource_link.return_value = "https://content/toc"
    api.download.return_value.content = toc.encode("utf-8")
    return api


def request(file_id="140796813", art_id="74208177"):
    return BookRequest(
        url="u", format=BookFormat.TEXT_READER, file_id=file_id, art_id=art_id
    )


def test_extractor_reads_toc_through_a_resource_link():
    api = make_toc_api()

    book = ReaderTextExtractor(api).get(request())

    api.resource_link.assert_called_once_with("140796813", "toc.js", "74208177")
    api.download.assert_called_once_with("https://content/toc")
    assert (book.file_id, book.art_id, book.base_url) == ("140796813", "74208177", "")
    assert book.meta.title == "Последнее па-де-де в темноте"
    assert [str(a) for a in book.meta.authors] == ["Мэри Вестчестер"]
    assert [p["url"] for p in book.parts] == ["part_0.json", "Part_1.json"]


def test_extractor_decodes_utf8_even_if_requests_guessed_latin1():
    api = make_toc_api()
    api.download.return_value.text = TOC.encode("utf-8").decode("latin-1")
    assert ReaderTextExtractor(api).get(request()).meta.title.startswith("Последнее")


def test_extractor_requires_file_id():
    with pytest.raises(BookProcessingError, match="file_id"):
        ReaderTextExtractor(make_toc_api()).get(request(file_id=None))


def test_extractor_wraps_network_and_decoding_errors():
    api = make_toc_api()
    api.resource_link.side_effect = requests.ConnectionError("down")
    with pytest.raises(BookProcessingError, match="toc retrieval error"):
        ReaderTextExtractor(api).get(request())

    api = make_toc_api()
    api.download.return_value.content = TOC.encode("cp1251")
    with pytest.raises(BookProcessingError, match="UTF-8"):
        ReaderTextExtractor(api).get(request())


# --- loader ------------------------------------------------------------------------


def make_book(parts=None) -> TextBook:
    meta = BookMeta(authors=[Author(first="A")], title="T", version=1.0, uuid="u")
    return TextBook(
        meta=meta,
        parts=parts or [{"url": "Part_0.json"}, {"url": "part_1.json"}],
        base_url="",
        file_id="140796813",
        art_id="74208177",
    )


def make_loader():
    """Loader over a fake API: signed resources and legacy json/ assets are dicts."""
    api = make_api()
    api.resource_link.side_effect = lambda file_id, resource, art_id=None: f"L:{resource}"
    signed: dict[str, bytes] = {}
    legacy: dict[str, bytes] = {}

    def body(content: bytes, content_type: str = "image/png"):
        resp = MagicMock()
        resp.content = content
        resp.headers = {"Content-Type": content_type}
        resp.iter_content.return_value = [content]
        return resp

    def download(link):
        return body(signed.get(link, b""))

    def legacy_asset(art_id, file_id, name):
        if name in legacy:
            return body(legacy[name])
        raise requests.HTTPError("404")

    api.download.side_effect = download
    api.legacy_asset.side_effect = legacy_asset
    return ReaderTextLoader(api), api, signed, legacy


def img(name: str) -> str:
    return '{"t": "img", "s": "%s"}' % name


def test_loader_saves_the_part_as_utf8_text(tmp_path):
    loader, api, signed, _ = make_loader()
    signed["L:Part_0.json"] = '[{"c": ["Привет"]}]'.encode()

    assert loader._download_part(0, make_book(), tmp_path) is True

    api.resource_link.assert_called_once_with("140796813", "Part_0.json", "74208177")
    assert (tmp_path / "0.txt").read_text(encoding="utf-8") == '[{"c": ["Привет"]}]'
    assert [p.name for p in tmp_path.iterdir()] == ["0.txt"]


def test_images_come_from_the_json_path_first(tmp_path):
    loader, api, signed, legacy = make_loader()
    signed["L:part_1.json"] = f"[{img('img_0.png')}, {img('img_0.png')}]".encode()
    legacy["img_0.png"] = b"PNGDATA"

    assert loader._download_part(1, make_book(), tmp_path) is True

    assert (tmp_path / "images" / "img_0.png").read_bytes() == b"PNGDATA"
    api.legacy_asset.assert_called_once_with("74208177", "140796813", "img_0.png")
    # only the part itself needed a signed link, and the image was fetched once
    assert [c.args[1] for c in api.resource_link.call_args_list] == ["part_1.json"]


def test_a_non_image_answer_from_the_json_path_falls_back_to_a_signed_link(tmp_path):
    loader, api, signed, _ = make_loader()
    signed["L:part_1.json"] = f"[{img('img_0.png')}]".encode()
    signed["L:img_0.png"] = b"REALPNG"
    html = MagicMock()
    html.headers = {"Content-Type": "text/html; charset=utf-8"}
    api.legacy_asset.side_effect = lambda a, f, n: html

    assert loader._download_part(1, make_book(), tmp_path) is True

    assert (tmp_path / "images" / "img_0.png").read_bytes() == b"REALPNG"
    html.close.assert_called_once()


def test_missing_images_are_downloaded_in_parallel_with_progress(tmp_path, mocker):
    loader, api, _, legacy = make_loader()
    loader._max_workers = 4
    names = [f"img_{i}.png" for i in range(6)]
    (tmp_path / "0.txt").write_text("[" + ",".join(img(n) for n in names[:3]) + "]", encoding="utf-8")
    (tmp_path / "1.txt").write_text("[" + ",".join(img(n) for n in names[2:]) + "]", encoding="utf-8")
    for n in names:
        legacy[n] = n.encode()
    info = mocker.patch("litres.loaders.reader_text_loader.logger.info")

    loader.download_parts(make_book(), BookPaths("book", tmp_path, tmp_path / "out"))

    assert sorted(p.name for p in (tmp_path / "images").iterdir()) == names
    assert api.legacy_asset.call_count == 6  # img_2 appears in both parts, fetched once
    info.assert_any_call("Downloading 6 missing images")


def test_images_fall_back_to_a_signed_link(tmp_path):
    loader, api, signed, _ = make_loader()
    signed["L:part_1.json"] = f"[{img('i_7.jpg')}]".encode()
    signed["L:i_7.jpg"] = b"JPEGDATA"

    assert loader._download_part(1, make_book(), tmp_path) is True

    assert (tmp_path / "images" / "i_7.jpg").read_bytes() == b"JPEGDATA"
    assert [c.args[1] for c in api.resource_link.call_args_list] == [
        "part_1.json",
        "i_7.jpg",
    ]


def test_loader_skips_images_it_already_has(tmp_path):
    loader, api, signed, _ = make_loader()
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "img_0.png").write_bytes(b"old")
    signed["L:part_1.json"] = f"[{img('img_0.png')}]".encode()

    loader._download_part(1, make_book(), tmp_path)

    assert (tmp_path / "images" / "img_0.png").read_bytes() == b"old"
    api.legacy_asset.assert_not_called()


def test_a_failed_image_does_not_fail_the_part(tmp_path, mocker):
    mocker.patch("litres.loaders.reader_loader.time.sleep")
    warn = mocker.patch("litres.loaders.reader_text_loader.logger.warning")
    loader, api, signed, _ = make_loader()
    signed["L:part_1.json"] = f"[{img('img_0.png')}]".encode()

    def links(file_id, resource, art_id=None):
        if resource == "img_0.png":
            raise requests.ConnectionError("down")
        return f"L:{resource}"

    api.resource_link.side_effect = links

    assert loader._download_part(1, make_book(), tmp_path) is True
    assert (tmp_path / "1.txt").exists()
    warn.assert_called_once()


def test_the_part_file_appears_only_after_its_images(tmp_path):
    loader, api, signed, legacy = make_loader()
    signed["L:part_1.json"] = f"[{img('img_0.png')}]".encode()
    legacy["img_0.png"] = b"x"
    seen = {}
    original = legacy.__getitem__

    def spy(name):
        seen["part_written_during_image_download"] = (tmp_path / "1.txt").exists()
        return original(name)

    api.legacy_asset.side_effect = lambda a, f, n: (
        spy(n) and MagicMock(iter_content=lambda *_: [b"x"])
    )

    loader._download_part(1, make_book(), tmp_path)

    assert seen == {"part_written_during_image_download": False}


def test_loader_retries_a_part_with_a_fresh_link(tmp_path, mocker):
    sleep = mocker.patch("litres.loaders.reader_loader.time.sleep")
    loader, api, signed, _ = make_loader()
    signed["L:part_1.json"] = b"[]"
    calls = []

    def links(file_id, resource, art_id=None):
        calls.append(resource)
        if len(calls) == 1:
            raise requests.HTTPError("403 expired")
        return f"L:{resource}"

    api.resource_link.side_effect = links

    assert loader._download_part(1, make_book(), tmp_path) is True
    assert calls == ["part_1.json", "part_1.json"]
    api.reset_drm.assert_called_once()
    sleep.assert_called_once()


def test_loader_gives_up_after_max_attempts(tmp_path, mocker):
    mocker.patch("litres.loaders.reader_loader.time.sleep")
    error = mocker.patch("litres.loaders.reader_text_loader.logger.error")
    loader, api, _, _ = make_loader()
    api.resource_link.side_effect = requests.ConnectionError("down")

    assert loader._download_part(0, make_book(), tmp_path) is False

    assert api.resource_link.call_count == MAX_ATTEMPTS
    error.assert_called_once()
    assert list(tmp_path.iterdir()) == []


def test_loader_rejects_a_part_that_is_not_utf8(tmp_path, mocker):
    error = mocker.patch("litres.loaders.reader_text_loader.logger.error")
    loader, _, signed, _ = make_loader()
    signed["L:Part_0.json"] = "привет".encode("cp1251")

    assert loader._download_part(0, make_book(), tmp_path) is False
    assert not (tmp_path / "0.txt").exists()
    error.assert_called_once()


def test_loader_needs_a_file_id(tmp_path, mocker):
    error = mocker.patch("litres.loaders.reader_text_loader.logger.error")
    loader, api, _, _ = make_loader()
    book = make_book()
    book.file_id = None

    assert loader._download_part(0, book, tmp_path) is False
    api.resource_link.assert_not_called()
    error.assert_called_once()


def test_a_rerun_fetches_images_missing_for_parts_that_are_already_on_disk(tmp_path):
    loader, api, _, legacy = make_loader()
    book = make_book()
    (tmp_path / "0.txt").write_text(f"[{img('img_0.png')}]", encoding="utf-8")
    (tmp_path / "1.txt").write_text(f"[{img('img_1.png')}]", encoding="utf-8")
    legacy["img_0.png"] = b"ZERO"
    legacy["img_1.png"] = b"ONE"
    paths = BookPaths("book", tmp_path, tmp_path / "out")

    loader.download_parts(book, paths)

    assert (tmp_path / "images" / "img_0.png").read_bytes() == b"ZERO"
    assert (tmp_path / "images" / "img_1.png").read_bytes() == b"ONE"
    api.resource_link.assert_not_called()  # the parts themselves were not fetched again


def test_a_rerun_leaves_existing_images_alone(tmp_path):
    loader, api, _, legacy = make_loader()
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "img_0.png").write_bytes(b"old")
    (tmp_path / "0.txt").write_text(f"[{img('img_0.png')}]", encoding="utf-8")
    (tmp_path / "1.txt").write_text("[]", encoding="utf-8")

    loader.download_parts(make_book(), BookPaths("book", tmp_path, tmp_path / "out"))

    assert (tmp_path / "images" / "img_0.png").read_bytes() == b"old"
    api.legacy_asset.assert_not_called()


# --- image_names -----------------------------------------------------------------


def test_image_names_reads_img_nodes_from_the_structure():
    text = (
        '[{t: "p", c: ["see img_9.png in prose"]},'
        ' {t: "div", c: [{t: "img", s: "img_0.png"}]},'
        ' {t: "img", src: "i_5.jpg"},]'
    )
    assert image_names(text) == ["i_5.jpg", "img_0.png"]


def test_image_names_ignores_unsafe_names():
    text = '[{"t": "img", "s": "../secret.png"}, {"t": "img", "s": "a/b.png"}, {"t": "img", "s": ".hidden"}]'
    assert image_names(text) == []


def test_image_names_falls_back_to_patterns_when_the_part_is_not_parseable():
    assert image_names("not json {{ img_3.png and i_4.jpg") == ["i_4.jpg", "img_3.png"]


def test_image_names_of_a_part_without_images():
    assert image_names('[{"t": "p", "c": ["text"]}]') == []
