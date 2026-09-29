import json

import requests

from litres.exceptions import BookProcessingError
from litres.models.book import BookRequest, TextBook
from litres.parsing import book_meta_from_dict
from litres.utils import js_object_to_json

O4_URL_TEMPLATE = "https://www.litres.ru{url}json/toc.js"


class O4Extractor:
    def __init__(self, session: requests.Session):
        self._session = session

    def get(self, bq: BookRequest) -> TextBook:
        """Fetch and parse text book metadata from LitRes using BookRequest."""
        base_url = bq.base_url
        if not base_url:
            raise BookProcessingError(f"No base_url in request for: {bq.url}")
        try:
            toc_url = O4_URL_TEMPLATE.format(url=base_url)
            response = self._session.get(toc_url)
            response.raise_for_status()
            return self._extract_o4_book_data(response.text, base_url)
        except requests.exceptions.RequestException as e:
            raise BookProcessingError(
                f"Text book metadata retrieval error: {e!s}"
            ) from e

    def _extract_o4_book_data(self, text: str, base_url: str) -> TextBook:
        try:
            # The response is not valid JSON, it's a JS object. It needs to be cleaned up.
            data = json.loads(js_object_to_json(text))
            meta_data = data.get("Meta", {})

            return TextBook(
                base_url=base_url,
                meta=book_meta_from_dict(
                    meta_data, default_title="Unknown", default_uuid=""
                ),
                parts=data.get("Parts", []),
            )
        except json.JSONDecodeError as e:
            raise BookProcessingError(f"Text book metadata retrieval error: {e}") from e
