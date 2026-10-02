import json
import re
from dataclasses import replace

import requests

from litres.exceptions import BookProcessingError
from litres.extractors.extras import find_extras
from litres.models.book import BookRequest, Page, PdfBook
from litres.parsing import book_meta_from_dict
from litres.services.litres_api import LitresApi
from litres.utils import js_object_to_json

DEFAULT_RESOLUTION = "w640"


def _variant_width(variant: dict) -> int:
    digits = re.sub(r"\D", "", str(variant.get("rt", "")))
    return int(digits) if digits else int(variant.get("w") or 0)


class ReaderPdfExtractor:
    """Reads a PDF book's config the way the /static/reader/pdf reader does."""

    def __init__(self, api: LitresApi):
        self._api = api

    def get(self, bq: BookRequest) -> PdfBook:
        file_id = bq.file_id
        if not file_id:
            raise BookProcessingError(f"No file_id in request for: {bq.url}")

        try:
            drm = self._api.drm_params(bq.art_id)
            config_url = self._api.file_link(
                file_id, index=1, is_trial="false", **drm
            )
            response = self._api.download(config_url)
            try:
                # The server sends no charset, so response.text would guess
                # ISO-8859-1 and mangle Cyrillic; the web reader reads UTF-8.
                text = response.content.decode("utf-8")
            finally:
                response.close()
        except requests.RequestException as e:
            raise BookProcessingError(
                f"Reader config retrieval error: {e!s}"
            ) from e
        except UnicodeDecodeError as e:
            raise BookProcessingError(f"Reader config is not valid UTF-8: {e}") from e

        book = self._parse_config(text, file_id, bq.art_id)
        return replace(book, extras=find_extras(self._api, bq.art_id))

    def _parse_config(self, text: str, file_id: str, art_id: str | None) -> PdfBook:
        """The config is a JS assignment (`... = {...};`) holding the book object."""
        try:
            body = text[text.index("=") + 1 :].strip().removesuffix(";")
            data = json.loads(js_object_to_json(body))
        except ValueError as e:
            raise BookProcessingError(f"Failed to parse reader config: {e}") from e

        variants = [
            v for v in data.get("pages", []) if isinstance(v, dict) and v.get("p")
        ]
        if not variants:
            raise BookProcessingError("Reader config has no page sizes")
        best = max(variants, key=_variant_width)  # sharpest variant available

        pages = [
            Page(
                width=int(p.get("w", 0)),
                height=int(p.get("h", 0)),
                extension=p.get("ext", ""),
            )
            for p in best["p"]
            if isinstance(p, dict)
        ]
        meta = book_meta_from_dict(
            data.get("Meta", {}),
            default_title=f"Unknown_{file_id}",
            default_uuid=file_id,
        )
        return PdfBook(
            file_id=file_id,
            meta=meta,
            parts=pages,
            art_id=art_id,
            resolution=best.get("rt") or DEFAULT_RESOLUTION,
        )
