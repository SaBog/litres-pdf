import json
import re
from urllib.parse import parse_qs, urlparse

import requests

from litres.config import logger
from litres.exceptions import BookProcessingError
from litres.models.book import Author, BookMeta, BookRequest, Page, PdfBook

o3_URL_TEMPLATE = "https://www.litres.ru/pages/get_pdf_js/?file={file_id}"


class ExtractO3BookCommand:
    def __init__(self, session: requests.Session):
        self._session = session

    def get(self, bq: BookRequest) -> PdfBook:
        """Fetch and parse book metadata from LitRes using BookRequest."""
        file_id = bq.file_id or self._extract_file_id(bq.url)
        if not file_id:
            raise BookProcessingError(f"Failed to extract file_id from URL: {bq.url}")
        try:
            url = o3_URL_TEMPLATE.format(file_id=file_id)
            response = self._session.get(url)
            response.raise_for_status()
            return self._extract_o3_book_data(response.text)
        except Exception as e:
            logger.error(f"Metadata retrieval error: {str(e)}", exc_info=True)
            raise BookProcessingError(f"Metadata retrieval error: {str(e)}")

    def _extract_file_id(self, url: str):
        """Извлечение ID книги из URL"""
        # Пытаемся извлечь ID из параметров запроса
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        if 'file' in query_params:
            return query_params['file'][0]
        elif 'art' in query_params:
            return query_params['art'][0]

        # This is a more specific match for book URLs like /book/author/title-12345/
        path_match = re.search(r"/book/.*-(\d+)/?$", parsed_url.path)
        if path_match:
            return path_match.group(1)

        # Пробуем извлечь ID из пути URL
        match = re.search(r"reader/(?:or/)?(\d+)", url)
        if match:
            return match.group(1)

        # Пробуем извлечь ID из короткой формы URL
        match = re.search(r"litres\.ru/(\d+)/?", url)
        if match:
            return match.group(1)

        return None

    def _extract_o3_book_data(self, response_text: str) -> PdfBook:
        """Parse book data from LitRes custom response (JSON or JS-wrapped)."""
        try:
            file_id_match = re.search(r"\[(\d+)\]", response_text)
            if not file_id_match:
                logger.error(
                    "Could not find file_id in response",
                    extra={"raw_response": response_text},
                )
                raise BookProcessingError("Could not find file_id in response")
            file_id = file_id_match.group(1)

            data = json.loads(re.sub(r"^[^{]*", "", response_text))
            meta_data, pages_data = data.get("Meta"), data.get("pages")

            if not (meta_data and pages_data):
                logger.warning(
                    "Meta or pages missing, using defaults",
                    extra={"raw_response": response_text},
                )
                book_meta = BookMeta(
                    authors=[], title=f"Unknown_{file_id}", version=0.0, uuid=file_id
                )
                pages = []
            else:
                authors = [
                    Author(
                        first=author.get("First", ""),
                        middle=author.get("Middle"),
                        last=author.get("Last"),
                    )
                    for author in meta_data.get("Authors", [])
                ]
                book_meta = BookMeta(
                    authors=authors,
                    title=meta_data.get("Title", f"Unknown_{file_id}"),
                    version=float(meta_data.get("version") or 0.0),
                    uuid=meta_data.get("UUID", file_id),
                )
                pages = [
                    Page(
                        width=int(p.get("w", 0)),
                        height=int(p.get("h", 0)),
                        extension=p.get("ext", "jpg"),
                    )
                    for page in pages_data
                    for p in page.get("p", [])
                ]

            return PdfBook(file_id=file_id, meta=book_meta, parts=pages)

        except Exception as e:
            logger.error(
                f"Failed to parse book data: {e}",
                exc_info=True,
                extra={"raw_response": response_text},
            )
            raise BookProcessingError(f"Failed to parse book data: {e}") 
