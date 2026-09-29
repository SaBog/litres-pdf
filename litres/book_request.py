import re
from urllib.parse import parse_qs, urlparse

import requests

from litres.exceptions import BookProcessingError
from litres.models.book import BookFormat, BookRequest
from litres.parsing import state_queries
from litres.utils import extract_initial_state

# Пример: https://www.litres.ru/book/author/book-title-12345/
_BOOK_PAGE_URL = re.compile(r".*/book/.+-\d+/?$")
_O3_VIEWER_PATH = "/static/or3/view/or.html"
_O4_VIEWER_PATH = "/static/or4/view/or.html"
_AUDIOBOOK_PATH = "/audiobook/"


class BookRequestResolver:
    """Resolves a user-supplied URL into a BookRequest (format plus the ids to fetch)."""

    def __init__(self, session: requests.Session):
        self._session = session

    def resolve(self, url: str) -> BookRequest:
        if _BOOK_PAGE_URL.match(url):
            return self._from_book_page(url)
        return self._from_direct_url(url)

    def _from_book_page(self, url: str) -> BookRequest:
        resp = self._session.get(url)
        resp.raise_for_status()
        state = extract_initial_state(resp.text)

        art_data, art_files = self._extract_art_data_and_files(state)
        book_format, file_id = self._detect_book_format_and_file(art_files)
        art_id = art_data.get("id") if art_data else None
        if not (book_format and file_id and art_id):
            raise BookProcessingError(
                f"Could not determine book format or file for: {url}"
            )

        return BookRequest(
            url=url,
            format=book_format,
            file_id=file_id,
            art_id=art_id,
            base_url=f"/download_book_subscr/{art_id}/{file_id}/",
        )

    def _from_direct_url(self, url: str) -> BookRequest:
        """Recognise viewer and audiobook URLs the user pasted directly."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        if _O3_VIEWER_PATH in parsed.path and "file" in query:
            return BookRequest(url=url, format=BookFormat.O3, file_id=query["file"][0])
        if _O4_VIEWER_PATH in parsed.path and "baseurl" in query:
            return BookRequest(
                url=url, format=BookFormat.O4, base_url=query["baseurl"][0]
            )
        if _AUDIOBOOK_PATH in parsed.path:
            return BookRequest(url=url, format=BookFormat.AUDIOBOOK)

        raise BookProcessingError(f"Unsupported URL format: {url}")

    def _extract_art_data_and_files(self, state):
        """Extract art_data and art_files from state structure."""
        art_data = None
        art_files = None
        for key, value in state_queries(state).items():
            if key.startswith("getArtData(") and "data" in value and art_data is None:
                art_data = value["data"]
            elif (
                key.startswith("getArtFiles(") and "data" in value and art_files is None
            ):
                art_files = value["data"]
        return art_data, art_files

    def _detect_book_format_and_file(self, art_files):
        """Detect book format (o3/o4) and select file_id based on file extensions."""
        o4_exts = {"txt", "txt.zip"}
        o3_exts = {"a4.pdf", "pdf", "a6.pdf"}
        file_id = None
        book_format = None
        # Сначала ищем по extension (старый способ)
        for f in art_files or []:
            ext = f.get("extension", "")
            if ext in o4_exts:
                file_id = f["id"]
                book_format = BookFormat.O4
                break
        if not file_id:
            for f in art_files or []:
                ext = f.get("extension", "")
                if ext in o3_exts:
                    file_id = f["id"]
                    book_format = BookFormat.O3
                    break
        # Новый способ: если не нашли — ищем по filename и encoding_type
        if not file_id:
            for f in art_files or []:
                filename = f.get("filename", "")
                encoding_type = f.get("encoding_type", "")
                if filename.endswith(".pdf") and encoding_type == "pdf_book":
                    file_id = f["id"]
                    book_format = BookFormat.O3
                    break
        return book_format, file_id
