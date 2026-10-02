from pathlib import Path

from litres.config import logger
from litres.exceptions import BookProcessingError
from litres.loaders.reader_loader import ReaderLoader
from litres.models.book import PdfBook

DEFAULT_RESOLUTION = "w640"


class ReaderPageLoader(ReaderLoader[PdfBook]):
    """Downloads page images through signed links, like the /static/reader/pdf reader."""

    def _download_part(self, part_num: int, book: PdfBook, source_dir: Path) -> bool:
        part = book.parts[part_num]
        filepath = source_dir / f"{part_num}.{part.extension}"
        try:
            response = self._fetch_signed(
                lambda: self._api.file_link(
                    book.file_id,
                    page_id=part_num,
                    is_trial="false",
                    resolution=book.resolution or DEFAULT_RESOLUTION,
                    image_type=part.extension,
                    **self._api.drm_params(book.art_id),
                )
            )
        except BookProcessingError as e:
            logger.error(f"Failed to download page {part_num}: {e!s}")
            return False
        self._save_response(response, filepath)
        return True
