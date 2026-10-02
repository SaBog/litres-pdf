import requests

from litres.constants import FILE_DOWNLOAD_URL
from litres.exceptions import BookProcessingError
from litres.models.book import AudioBook, AudioPart, Author, BookMeta, BookRequest
from litres.parsing import extra_files
from litres.services.litres_api import LitresApi
from litres.utils import natural_key

AUDIO_ENCODING = "standard_quality_mp3"  # the book itself, not sample/m4b/zip/bonus


class AudiobookExtractor:
    """Lists an audiobook's mp3 parts from the files API."""

    def __init__(self, api: LitresApi):
        self._api = api

    def get(self, bq: BookRequest) -> AudioBook:
        art_id = bq.art_id
        if not art_id:
            raise BookProcessingError(f"No art id in request for: {bq.url}")

        try:
            art = self._api.art(art_id)
            files = self._api.art_files(art_id)
        except requests.RequestException as e:
            raise BookProcessingError(
                f"Audiobook metadata retrieval error: {e!s}"
            ) from e

        parts = self._parts(art_id, files)
        if not parts:
            raise BookProcessingError(f"No audio parts listed for art {art_id}")
        return AudioBook(
            meta=self._meta(art),
            art_id=art_id,
            parts=parts,
            extras=extra_files(art_id, files),
        )

    @staticmethod
    def _meta(art: dict) -> BookMeta:
        title = "Аудиокнига"
        if book_title := art.get("title"):
            title += f" {book_title}"
        authors = [Author(first="Litres")]  # TODO: можно доработать авторов
        return BookMeta(
            authors=authors,
            title=title,
            version=1.0,
            uuid=str(art.get("uuid") or "audiobook"),
        )

    @staticmethod
    def _parts(art_id: str, files: list[dict]) -> list[AudioPart]:
        """Standard-quality mp3 files in listening order (00, 01, ... 10, 11)."""
        mp3_files = [
            f
            for f in files
            if f.get("encoding_type") == AUDIO_ENCODING
            and not f.get("is_additional")
            and str(f.get("filename", "")).lower().endswith(".mp3")
        ]
        mp3_files.sort(key=lambda f: natural_key(f["filename"]))
        return [
            {
                "filename": f["filename"],
                "file_id": str(f["id"]),
                "url": FILE_DOWNLOAD_URL.format(
                    art_id=art_id, file_id=f["id"], filename=f["filename"]
                ),
            }
            for f in mp3_files
        ]
