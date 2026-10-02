from pathlib import Path

from litres.config import logger
from litres.constants import FILE_DOWNLOAD_URL
from litres.loaders.base_loader import BaseLoader
from litres.models.book import AudioBook


class AudioLoader(BaseLoader[AudioBook]):
    def _download_part(self, part_num: int, book: AudioBook, source_dir: Path) -> bool:
        part = book.parts[part_num]
        url = FILE_DOWNLOAD_URL.format(
            art_id=book.art_id,
            file_id=part["file_id"],
            filename=part["filename"],
        )
        filepath = source_dir / f"{part_num}.mp3"

        try:
            response = self._fetch_with_retry(url)
            self._ensure_not_a_page(response)
            self._save_response(response, filepath)
            return True
        except Exception as e:
            logger.error(f"Failed to download {part_num}: {e}")
            return False
