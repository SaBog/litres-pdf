from pathlib import Path

from litres.config import logger
from litres.loaders.base_loader import BaseLoaderCommand
from litres.models import Book
from litres.models.book import PdfBook

URL_TEMPLATE = "https://www.litres.ru/pages/get_pdf_page/?file={file_id}&page={part_num}&rt=w{w}&ft={file_type}"
DEFAULT_CHUNK_SIZE = 8192


class ImgLoaderCommand(BaseLoaderCommand):
    def _download_part(self, part_num: int, book: Book, source_dir: Path) -> bool:
        """Download a single part with retry logic."""
        assert isinstance(book, PdfBook), f"Expected PdfBook, got {type(book).__name__}"

        part = book.parts[part_num]
        url = URL_TEMPLATE.format(
            file_id=book.file_id,
            part_num=part_num,
            w=part.width,
            file_type=part.extension
        )
        filename = f"{part_num}.{part.extension}"
        filepath = source_dir / filename

        try:
            response = self._fetch_with_retry(url, filepath)
            with filepath.open('wb') as f:
                for chunk in response.iter_content(DEFAULT_CHUNK_SIZE):
                    f.write(chunk)

            return True
        except Exception as e:
            logger.error(f"Failed to download part {part_num}: {e}")
            return False