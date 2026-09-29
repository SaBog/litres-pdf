from litres.engines.o4.processors.content_processor import ContentNode
from litres.engines.o4.processors.fb2_processor import FB2ContentProcessor
from litres.engines.o4.processors.pdf_processor import PDFContentProcessor


def test_get_image_src_prefers_s_then_src_and_only_for_img():
    assert ContentNode({"t": "img", "s": "i_1.jpg"}).get_image_src() == "i_1.jpg"
    assert ContentNode({"t": "img", "src": "i_2.png"}).get_image_src() == "i_2.png"
    assert ContentNode({"t": "img"}).get_image_src() is None
    assert ContentNode({"t": "p", "s": "i_1.jpg"}).get_image_src() is None


def test_soft_hyphens_are_removed_from_text():
    node = ContentNode({"t": "p", "c": ["hy­phen", "ated"]})
    assert node.get_text() == "hyphenated"


def test_pdf_processor_collects_existing_images_only(tmp_path):
    (tmp_path / "i_1.jpg").write_bytes(b"x")
    processor = PDFContentProcessor(tmp_path)

    text = processor.process_structure(
        [
            {"t": "img", "s": "i_1.jpg"},
            {"t": "img", "s": "i_missing.jpg"},
            {"t": "p", "c": ["hello"]},
        ]
    )

    assert "[IMAGE: i_1.jpg]" in text
    assert "i_missing" not in text
    assert "hello" in text
    assert [p.name for p in processor.get_images()] == ["i_1.jpg"]


def test_pdf_processor_marks_headings():
    processor = PDFContentProcessor(None)  # ty: ignore[invalid-argument-type]
    text = processor.process_structure([{"t": "h1", "c": ["Chapter"]}])
    assert processor.parse_content_with_headings(text) == [("Chapter", True)]


def test_fb2_processor_references_and_embeds_images(tmp_path):
    (tmp_path / "i_1.jpg").write_bytes(b"data")
    processor = FB2ContentProcessor(tmp_path)

    body = processor.process_structure([{"t": "img", "s": "i_1.jpg"}])
    binaries = processor.generate_binaries()

    assert 'l:href="#img1"' in body
    assert '<binary id="img1" content-type="image/jpeg">' in binaries


def test_fb2_processor_escapes_text():
    processor = FB2ContentProcessor(None)  # ty: ignore[invalid-argument-type]
    body = processor.process_structure([{"t": "p", "c": ["a < b & c"]}])
    assert "a &lt; b &amp; c" in body
