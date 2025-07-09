import json
import re
from urllib.parse import parse_qs, urlparse
import requests

from litres.exceptions import BookProcessingError
from litres.models.book import Author, Book, BookMeta, BookRequest, TextBook

o4_URL_TEMPLATE = "https://www.litres.ru{url}json/toc.js"


class ExtractO4BookCommand:
    def __init__(self, session: requests.Session):
        self._session = session

    def get(self, bq: BookRequest):
        """Fetch and parse text book metadata from LitRes using BookRequest."""
        base_url = bq.base_url or self._extract_base_url(bq.url)
        if not base_url:
            raise BookProcessingError(f"Failed to extract base_url from URL: {bq.url}")
        try:
            toc_url = o4_URL_TEMPLATE.format(url=base_url)
            response = self._session.get(toc_url)
            response.raise_for_status()
            return self._extract_o4_book_data(response.text, base_url)
        except requests.exceptions.RequestException as e:
            raise BookProcessingError(f"Text book metadata retrieval error: {str(e)}")
        
    def _extract_base_url(self, url: str) -> str | None:
        """Extracts the base_url from a subscription book URL."""
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            return query_params.get('baseurl', [None])[0]
        except (AttributeError, IndexError):
            return None
    
    def _extract_o4_book_data(self, text: str, base_url: str) -> Book:
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
        