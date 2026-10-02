import re
from urllib.parse import parse_qs, urlparse

import requests

from litres.exceptions import BookProcessingError
from litres.models.book import BookFormat, BookRequest
from litres.services.litres_api import LitresApi

# Пример: https://www.litres.ru/book/author/book-title-12345/
_BOOK_PAGE_URL = re.compile(r".*/book/.+-\d+/?$")
_ART_ID_AT_END = re.compile(r"-(\d+)/?$")
_O3_VIEWER_PATH = "/static/or3/view/or.html"
_O4_VIEWER_PATH = "/static/or4/view/or.html"
_READER_PDF_PATH = "/static/reader/pdf/index.html"
_READER_TEXT_PATH = "/static/reader/text/index.html"
_AUDIOBOOK_PATH = "/audiobook/"

_TEXT_FILE_EXTENSIONS = ("fb3", "txt", "txt.zip")
_PDF_FILE_EXTENSIONS = ("a4.pdf", "pdf", "a6.pdf")
_PDF_BOOK_ENCODING = "pdf_book"  # the full book, not the fragment or extras


class BookRequestResolver:
    """Resolves a user-supplied URL into a BookRequest (format plus the ids to fetch)."""

    def __init__(self, session: requests.Session, api: LitresApi | None = None):
        self._session = session
        self._api = api or LitresApi(session)

    def resolve(self, url: str) -> BookRequest:
        if _BOOK_PAGE_URL.match(url):
            return self._from_book_page(url)
        return self._from_direct_url(url)

    def _from_book_page(self, url: str) -> BookRequest:
        """A book page: the art id ends the URL and the API lists its files."""
        match = _ART_ID_AT_END.search(urlparse(url).path)
        if not match:
            raise BookProcessingError(f"Unsupported URL format: {url}")
        art_id = match.group(1)
        files = self._list_files(art_id)

        if file_id := self._text_file(files):
            book_format = BookFormat.TEXT_READER
        elif file_id := self._pdf_file(files):
            book_format = BookFormat.PDF_READER
        else:
            raise BookProcessingError(f"No readable text or PDF file found for: {url}")
        return BookRequest(url=url, format=book_format, file_id=file_id, art_id=art_id)

    def _from_direct_url(self, url: str) -> BookRequest:
        """Recognise viewer and audiobook URLs the user pasted directly."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        if _O3_VIEWER_PATH in parsed.path and "file" in query:
            return BookRequest(url=url, format=BookFormat.O3, file_id=query["file"][0])
        if _READER_TEXT_PATH in parsed.path and "art" in query:
            return self._from_text_reader(url, query)
        if _READER_PDF_PATH in parsed.path and "file" in query:
            return BookRequest(
                url=url,
                format=BookFormat.PDF_READER,
                file_id=query["file"][0],
                art_id=query.get("art", [None])[0],
            )
        if _O4_VIEWER_PATH in parsed.path and "baseurl" in query:
            return BookRequest(
                url=url, format=BookFormat.O4, base_url=query["baseurl"][0]
            )
        if _AUDIOBOOK_PATH in parsed.path:
            return self._from_audiobook_page(url, parsed.path)

        raise BookProcessingError(f"Unsupported URL format: {url}")

    def _from_audiobook_page(self, url: str, path: str) -> BookRequest:
        """An audiobook page: the art id ends the URL, the files come from the API."""
        match = _ART_ID_AT_END.search(path)
        if not match:
            raise BookProcessingError(f"Unsupported URL format: {url}")
        return BookRequest(url=url, format=BookFormat.AUDIOBOOK, art_id=match.group(1))

    def _from_text_reader(self, url: str, query: dict[str, list[str]]) -> BookRequest:
        """The text reader needs `art`; the file comes from `file`, `baseurl` or the API."""
        if query.get("trials", ["0"])[0] == "1":
            raise BookProcessingError(
                f"Trial (fragment) reader links are not supported: {url}"
            )

        art_id = query["art"][0]
        file_id = query.get("file", [None])[0] or self._file_id_from_baseurl(
            query.get("baseurl", [None])[0]
        )
        if not file_id:
            file_id = self._text_file(self._list_files(art_id))
        if not file_id:
            raise BookProcessingError(f"No readable text file listed for art {art_id}")
        return BookRequest(
            url=url, format=BookFormat.TEXT_READER, file_id=file_id, art_id=art_id
        )

    def _list_files(self, art_id: str) -> list[dict]:
        try:
            return self._api.art_files(art_id)
        except requests.RequestException as e:
            raise BookProcessingError(
                f"Could not list files for art {art_id}: {e!s}"
            ) from e

    @staticmethod
    def _file_id_from_baseurl(baseurl: str | None) -> str | None:
        """/download_book_subscr/<art>/<file>/ -> <file>"""
        if not baseurl:
            return None
        segment = baseurl.rstrip("/.").rsplit("/", 1)[-1]
        return segment if segment.isdigit() else None

    @staticmethod
    def _text_file(files: list[dict]) -> str | None:
        """The listing holds old versions without extensions; the current one has them."""
        by_extension = {f["extension"]: f["id"] for f in files if f.get("extension")}
        for extension in _TEXT_FILE_EXTENSIONS:
            if extension in by_extension:
                return str(by_extension[extension])
        return None

    @staticmethod
    def _pdf_file(files: list[dict]) -> str | None:
        """A PDF book: a file with a pdf extension, or the one encoded as `pdf_book`."""
        for f in files:
            if f.get("extension") in _PDF_FILE_EXTENSIONS:
                return str(f["id"])
        for f in files:
            if f.get("encoding_type") == _PDF_BOOK_ENCODING and not f.get(
                "is_additional"
            ):
                return str(f["id"])
        return None
