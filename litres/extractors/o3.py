import json
import re

import requests

from litres.config import logger
from litres.exceptions import BookProcessingError
from litres.models.book import BookRequest, Page, PdfBook
from litres.parsing import book_meta_from_dict
from litres.utils import js_object_to_json

O3_URL_TEMPLATE = "https://www.litres.ru/pages/get_pdf_js/?file={file_id}"


class O3Extractor:
    def __init__(self, session: requests.Session):
        self._session = session

    def get(self, bq: BookRequest) -> PdfBook:
        """Fetch and parse book metadata from LitRes using BookRequest."""
        file_id = bq.file_id
        if not file_id:
            raise BookProcessingError(f"No file_id in request for: {bq.url}")
        try:
            url = O3_URL_TEMPLATE.format(file_id=file_id)
            response = self._session.get(url)
            response.raise_for_status()
            return self._extract_o3_book_data(response.text)
        except Exception as e:
            logger.error(f"Metadata retrieval error: {e!s}", exc_info=True)
            raise BookProcessingError(f"Metadata retrieval error: {e!s}") from e

    def _extract_o3_book_data(self, response_text: str) -> PdfBook:
        """Extracts and parses book data from the custom JS object response."""
        try:
            # Extract file_id
            file_id_match = re.search(r"\[(\d+)\]", response_text)
            if not file_id_match:
                logger.error(
                    "Could not find file_id in response",
                    extra={"raw_response": response_text},
                )
                raise BookProcessingError("Could not find file_id in response")
            file_id = file_id_match.group(1)

            # Extract the main object content between the curly braces
            main_object_match = re.search(
                r"= \s*(\{.*\})\s*;?\s*$", response_text, re.DOTALL
            )
            if not main_object_match:
                logger.error(
                    "Could not find main object in response",
                    extra={"raw_response": response_text},
                )
                raise BookProcessingError("Could not find main object in response")

            object_content = main_object_match.group(1)

            normalized_content = js_object_to_json(object_content)

            # Parse the normalized JSON
            data = json.loads(normalized_content)
            meta_data = data.get("Meta", {})

            book_meta = book_meta_from_dict(
                meta_data, default_title=f"Unknown_{file_id}", default_uuid=file_id
            )

            # Extract pages information
            pages = []
            pages_data = data.get("pages", [])
            if pages_data and isinstance(pages_data, list) and len(pages_data) > 0:
                page_info = pages_data[0]  # First (and usually only) page group
                page_objects = page_info.get("p", [])

                for page_obj in page_objects:
                    if isinstance(page_obj, dict):
                        pages.append(
                            Page(
                                width=int(page_obj.get("w", 0)),
                                height=int(page_obj.get("h", 0)),
                                extension=page_obj.get("ext", ""),
                            )
                        )

            return PdfBook(file_id=file_id, meta=book_meta, parts=pages)

        except (KeyError, TypeError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed to parse book data: {e}",
                exc_info=True,
                extra={"raw_response": response_text},
            )
            raise BookProcessingError(f"Failed to parse book data: {e}") from e
