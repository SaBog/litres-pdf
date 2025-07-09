import json
import re
from urllib.parse import parse_qs, urlparse
import requests

from litres.exceptions import BookProcessingError
from litres.models.book import Author, Book, BookMeta, BookRequest, Page, PdfBook
from litres.config import logger

o3_URL_TEMPLATE = "https://www.litres.ru/pages/get_pdf_js/?file={file_id}"


class ExtractO3BookCommand:
    def __init__(self, session: requests.Session):
        self._session = session

    def get(self, bq: BookRequest):
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
        path_match = re.search(r'/book/.*-(\d+)/?$', parsed_url.path)
        if path_match:
            return path_match.group(1)

        # Пробуем извлечь ID из пути URL
        match = re.search(r'reader/(?:or/)?(\d+)', url)
        if match:
            return match.group(1)
        
        # Пробуем извлечь ID из короткой формы URL
        match = re.search(r'litres\.ru/(\d+)/?', url)
        if match:
            return match.group(1)
        
        return None


    def _extract_o3_book_data(self, response_text: str) -> Book:
        """Extracts and parses book data from the custom JS object response."""
        try:
            # The file_id is also present in the response, let's use it.
            file_id_match = re.search(r'\[(\d+)\]', response_text)
            if not file_id_match:
                logger.error("Could not find file_id in response", extra={"raw_response": response_text})
                raise BookProcessingError("Could not find file_id in response")
            file_id = file_id_match.group(1)

            # Extract JSON from the 'Meta' section using regex
            meta_match = re.search(r'Meta:\s*({.*?}),\s*pages:', response_text, re.DOTALL)
            if not meta_match:
                logger.error("Could not find 'Meta' JSON in response", extra={"raw_response": response_text})
                raise BookProcessingError("Could not find 'Meta' JSON in response")
            
            meta_data = json.loads(meta_match.group(1))

            # Extract authors using original capitalized keys
            authors_data = meta_data.get("Authors", [])
            authors = [
                Author(
                    first=author.get("First", ""),
                    middle=author.get("Middle"),
                    last=author.get("Last")
                ) for author in authors_data if isinstance(author, dict)
            ]

            # Create BookMeta object, handling potential empty version string
            book_meta = BookMeta(
                authors=authors,
                title=meta_data.get("Title", "Unknown"),
                version=float(meta_data.get("version") or 0.0),
                uuid=meta_data.get("UUID", "")
            )

            # Extract pages information using regex
            pages_match = re.search(r'pages:\s*\[\{p:\[([^\]]+)\]', response_text)
            pages = []
            if pages_match:
                pages_str = pages_match.group(1)
                page_objects = re.findall(r'\{\s*w:\s*(\d+),\s*h:\s*(\d+),\s*ext:\s*\'([^\']+)\'\s*\}', pages_str)
                for width_str, height_str, ext in page_objects:
                    pages.append(Page(
                        width=int(width_str),
                        height=int(height_str),
                        extension=ext
                    ))
            
            return PdfBook(
                file_id=file_id,
                meta=book_meta,
                parts=pages
            )
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse book data: {e}", exc_info=True, extra={"raw_response": response_text})
            raise BookProcessingError(f"Failed to parse book data: {e}") 
