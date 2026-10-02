from dataclasses import replace

import requests

from litres.exceptions import BookProcessingError
from litres.extractors.extras import find_extras
from litres.extractors.o4 import parse_o4_toc
from litres.models.book import BookRequest, TextBook
from litres.services.litres_api import LitresApi

TOC_RESOURCE = "toc.js"


class ReaderTextExtractor:
    """Reads a text book's table of contents the way the /static/reader/text reader does."""

    def __init__(self, api: LitresApi):
        self._api = api

    def get(self, bq: BookRequest) -> TextBook:
        file_id = bq.file_id
        if not file_id:
            raise BookProcessingError(f"No file_id in request for: {bq.url}")

        try:
            link = self._api.resource_link(file_id, TOC_RESOURCE, bq.art_id)
            response = self._api.download(link)
            try:
                # The server sends no charset; the web reader reads UTF-8
                text = response.content.decode("utf-8")
            finally:
                response.close()
        except requests.RequestException as e:
            raise BookProcessingError(f"Reader toc retrieval error: {e!s}") from e
        except UnicodeDecodeError as e:
            raise BookProcessingError(f"Reader toc is not valid UTF-8: {e}") from e

        book = parse_o4_toc(text, base_url="")
        return replace(
            book,
            file_id=file_id,
            art_id=bq.art_id,
            extras=find_extras(self._api, bq.art_id),
        )
