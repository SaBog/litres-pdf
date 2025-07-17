from litres.models.book import (Author, Book, BookMeta, BookRequest, Page,
                                PdfBook, TextBook)


def test_author_full_name():
    a = Author(first="Ivan", middle="Ivanovich", last="Petrov")
    assert a.full_name() == "Ivan Ivanovich Petrov"
    assert str(a) == "Ivan Ivanovich Petrov"
    a2 = Author(first="Ivan", last="Petrov")
    assert a2.full_name() == "Ivan Petrov"
    a3 = Author(first="Ivan")
    assert a3.full_name() == "Ivan"

def test_page():
    p = Page(width=100, height=200, extension="jpg")
    assert p.width == 100
    assert p.height == 200
    assert p.extension == "jpg"

def test_bookmeta():
    meta = BookMeta(authors=[Author(first="A")], title="Title", version=1.0, uuid="uuid")
    assert meta.title == "Title"
    assert meta.uuid == "uuid"
    assert isinstance(meta.authors[0], Author)

def test_book_total_parts():
    meta = BookMeta(authors=[], title="T", version=1.0, uuid="id")
    b = Book(meta=meta, parts=[1,2,3])
    assert b.total_parts == 3

def test_pdfbook_inherits_book():
    meta = BookMeta(authors=[], title="T", version=1.0, uuid="id")
    b = PdfBook(meta=meta, file_id="fid", parts=[Page(1,2,"jpg")])
    assert isinstance(b, Book)
    assert b.file_id == "fid"
    assert isinstance(b.parts[0], Page)

def test_textbook_inherits_book():
    meta = BookMeta(authors=[], title="T", version=1.0, uuid="id")
    b = TextBook(meta=meta, parts=[], base_url="url")
    assert isinstance(b, Book)
    assert b.base_url == "url"

def test_bookrequest():
    br = BookRequest(url="url", file_id="fid", art_id="aid", base_url="burl")
    assert br.url == "url"
    assert br.file_id == "fid"
    assert br.art_id == "aid"
    assert br.base_url == "burl" 