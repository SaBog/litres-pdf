from pathlib import Path

from litres.config import logger
from litres.loaders.base_loader import BaseLoaderCommand
from litres.models.book import AudioBook

URL_TEMPLATE ="https://www.litres.ru/download_book_subscr/{art_id}/{file_id}/{filename}"


class AudioLoaderCommand(BaseLoaderCommand[AudioBook]):
    def _download_part(self, part_num: int, book: AudioBook, source_dir: Path) -> bool:
        part = book.parts[part_num]
        url = URL_TEMPLATE.format(
            art_id=book.art_id,
            file_id=part["file_id"],
            filename=part["filename"],
        )
        filepath = source_dir / f"{part_num}.mp3"

        try:
            response = self._fetch_with_retry(url, filepath)
            with filepath.open('wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Failed to download {part_num}: {e}")
            return False 