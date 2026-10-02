
from litres.engines.audio_merge import AudioMergeEngine
from litres.extractors.o3 import O3Extractor
from litres.extractors.o4 import O4Extractor
from litres.models.out_format import OutFormat
from litres.parsing import book_meta_from_dict


def test_book_meta_from_dict_maps_authors_and_defaults():
    meta = book_meta_from_dict(
        {
            "Title": "T",
            "version": "2.5",
            "UUID": "u1",
            "Authors": [
                {"First": "Ivan", "Middle": "I.", "Last": "Petrov"},
                {"First": "Solo", "Middle": ""},
                "not-a-dict",
            ],
        },
        default_title="d",
        default_uuid="du",
    )
    assert (meta.title, meta.version, meta.uuid) == ("T", 2.5, "u1")
    assert [str(a) for a in meta.authors] == ["Ivan I. Petrov", "Solo"]
    assert meta.authors[1].middle is None


def test_book_meta_from_dict_uses_defaults_when_keys_missing():
    meta = book_meta_from_dict({}, default_title="Unknown_1", default_uuid="1")
    assert (meta.title, meta.uuid, meta.version, meta.authors) == (
        "Unknown_1",
        "1",
        0.0,
        [],
    )


O3_RESPONSE = """
var x = window.pdf[123] = {
  Meta: {Title: 'Война: и мир', Authors: [{First: 'Лев', Last: 'Толстой'}], version: 1, UUID: 'uu'},
  pages: [{p: [{w: 100, h: 200, ext: 'jpg'}, {w: 110, h: 210, ext: 'png'}]}]
};
"""


def test_o3_extractor_parses_meta_and_pages():
    book = O3Extractor(None)._extract_o3_book_data(O3_RESPONSE)  # ty: ignore[invalid-argument-type]

    assert book.file_id == "123"
    assert book.meta.title == "Война: и мир"
    assert str(book.meta.authors[0]) == "Лев Толстой"
    assert [(p.width, p.height, p.extension) for p in book.parts] == [
        (100, 200, "jpg"),
        (110, 210, "png"),
    ]


def test_o4_extractor_parses_meta_and_parts():
    text = "{Meta: {Title: 'Book', UUID: 'u', Authors: [{First: 'A'}],}, Parts: [{url: 'p1',}, {url: 'p2'}],}"
    book = O4Extractor(None)._extract_o4_book_data(text, "/base/")  # ty: ignore[invalid-argument-type]

    assert book.base_url == "/base/"
    assert (book.meta.title, book.meta.uuid) == ("Book", "u")
    assert [p["url"] for p in book.parts] == ["p1", "p2"]


def test_engine_supports_a_single_format():
    engine = AudioMergeEngine()
    assert engine.supports(OutFormat.MP3) is True
    assert engine.supports(OutFormat.PDF) is False
