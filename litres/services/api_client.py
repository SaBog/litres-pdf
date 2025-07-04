import re
import json
import requests

from litres.models.book import PdfBook
from litres.utils import extract_base_url, extract_file_id

from ..models import Author, Book, BookMeta, Page, TextBook
from ..exceptions import BookProcessingError
from ..config import logger

o3_URL_TEMPLATE = "https://www.litres.ru/pages/get_pdf_js/?file={file_id}"
o4_URL_TEMPLATE = "https://www.litres.ru{url}json/toc.js"

class LitresAPIClient:
    """Handles communication with the LitRes API."""

    def __init__(self, session: requests.Session):
        self._session = session

    def get_o4_book(self, url: str) -> TextBook:
        """Fetch and parse text book metadata from LitRes."""
        base_url = extract_base_url(url)

        if not base_url:
            raise BookProcessingError(f"Failed to extract base_url from URL: {url}")
        
        try:
            toc_url = o4_URL_TEMPLATE.format(url=base_url)
            response = self._session.get(toc_url)
            response.raise_for_status()

            return self.parse_litres_o3_response(response.text, base_url)
        except requests.exceptions.RequestException as e:
            raise BookProcessingError(f"Text book metadata retrieval error: {str(e)}")

    def parse_litres_o3_response(self, text: str, base_url: str):
        try:
            # The response is not valid JSON, it's a JS object. It needs to be cleaned up.
            text_data = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', text)
            text_data = re.sub(r',\s*([}\]])', r'\1', text_data)

            data = json.loads(text_data)
            meta_data = data.get("Meta", {})
            
            # Extract authors using original capitalized keys
            authors_data = meta_data.get("Authors", [])
            authors = [
                Author(
                    first=author.get("First", ""),
                    middle=author.get("Middle"),
                    last=author.get("Last")
                ) for author in authors_data if isinstance(author, dict)
            ]

            return TextBook(
                base_url=base_url,
                meta=BookMeta(
                    title=meta_data.get("Title", "Unknown"),
                    authors=authors,
                    version=float(meta_data.get("version") or 0.0),
                    uuid=meta_data.get("UUID", "")
                ),
                parts=data.get("Parts", [])
            )
        except json.JSONDecodeError as e:
            raise BookProcessingError(f"Text book metadata retrieval error", e)
        
    def get_o3_book(self, url: str) -> Book:
        """Fetch and parse book metadata from LitRes."""
        file_id = extract_file_id(url)
        
        if not file_id:
            raise BookProcessingError(f"Failed to extract file_id from URL: {url}")
        
        try:
            url = o3_URL_TEMPLATE.format(file_id=file_id)
            response = self._session.get(url)
            response.raise_for_status()

            return self._extract_book_data(response.text)
        except Exception as e:
            logger.error(f"Metadata retrieval error: {str(e)}", exc_info=True)
            raise BookProcessingError(f"Metadata retrieval error: {str(e)}")

    def _extract_book_data(self, response_text: str) -> Book:
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