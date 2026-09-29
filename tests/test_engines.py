import xml.etree.ElementTree as ET

import pytest

from litres.engines.audio_merge import AudioMergeEngine
from litres.engines.o4.fb2_engine import FB2Engine
from litres.engines.o4.pdf_engine import PDFEngine
from litres.exceptions import BookProcessingError
from litres.models.book import Author, Book, BookMeta
from litres.models.book_paths import BookPaths


def make_paths(tmp_path, filename="book"):
    paths = BookPaths(
        filename=filename, source=tmp_path / "src", output=tmp_path / "out"
    )
    paths.makedirs()
    return paths


def make_book(title="Title", authors=None):
    meta = BookMeta(
        authors=authors or [Author(first="A")], title=title, version=1.0, uuid="u"
    )
    return Book(meta=meta, parts=[])


def test_audio_merge_orders_parts_numerically(tmp_path):
    paths = make_paths(tmp_path)
    for i in (0, 1, 2, 10):
        (paths.source / f"{i}.mp3").write_bytes(f"[{i}]".encode())
    AudioMergeEngine().execute(make_book(), paths)
    assert (paths.output / "book.mp3").read_bytes() == b"[0][1][2][10]"


def test_audio_merge_without_files_raises(tmp_path):
    with pytest.raises(BookProcessingError):
        AudioMergeEngine().execute(make_book(), make_paths(tmp_path))


@pytest.mark.parametrize("engine", [PDFEngine(), FB2Engine()])
def test_text_engines_raise_when_no_content(tmp_path, engine):
    with pytest.raises(BookProcessingError):
        engine.execute(make_book(), make_paths(tmp_path))


def test_text_engines_raise_on_processing_failure(tmp_path, mocker):
    paths = make_paths(tmp_path)
    (paths.source / "0.txt").write_text('[{"t": "p", "c": ["x"]}]', encoding="utf-8")
    mocker.patch(
        "litres.engines.o4.fb2_engine.FB2ContentProcessor.process_structure",
        side_effect=RuntimeError("boom"),
    )
    with pytest.raises(BookProcessingError, match="boom"):
        FB2Engine().execute(make_book(), paths)


def test_fb2_escapes_title_and_authors(tmp_path):
    paths = make_paths(tmp_path)
    (paths.source / "0.txt").write_text('[{"t": "p", "c": ["x"]}]', encoding="utf-8")
    book = make_book(
        title="Tom & <Jerry>", authors=[Author(first="A&B", middle="<m>", last="C&D")]
    )
    FB2Engine().execute(book, paths)

    root = ET.parse(paths.output / "book.fb2").getroot()
    ns = {"f": "http://www.gribuser.ru/xml/fictionbook/2.0"}
    assert root.findtext(".//f:book-title", namespaces=ns) == "Tom & <Jerry>"
    assert root.findtext(".//f:first-name", namespaces=ns) == "A&B"


def _media_boxes(pdf_bytes: bytes) -> list[tuple[float, float]]:
    import re

    return [
        (float(w), float(h))
        for w, h in re.findall(
            rb"/MediaBox \[0(?:\.0+)? 0(?:\.0+)? ([\d.]+) ([\d.]+)\]", pdf_bytes
        )
    ]


def test_o3_engine_keeps_page_aspect_ratio(tmp_path):
    from PIL import Image

    from litres.engines.o3.pdf_engine import IMG2PDFEngine

    paths = make_paths(tmp_path)
    sizes = {0: (400, 800), 1: (800, 400), 2: (420, 594)}  # tall, wide, A-ratio
    for i, size in sizes.items():
        Image.new("RGB", size, "white").save(paths.source / f"{i}.jpg")

    IMG2PDFEngine(quality=50, dpi=0).execute(make_book(), paths)

    # The first MediaBox is the document-wide default; per-page boxes follow it
    boxes = _media_boxes((paths.output / "book.pdf").read_bytes())[1:]
    assert len(boxes) == 3
    for (w, h), (img_w, img_h) in zip(boxes, sizes.values(), strict=True):
        assert w / h == pytest.approx(img_w / img_h, rel=0.01)
