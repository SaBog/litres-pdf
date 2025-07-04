from pathlib import Path
from litres.models.book import Book
from litres.services.loaders.loader import Loader

from ...config import logger
from ...models import TextBook

class TextLoader(Loader):
    def _download_part(self, part_num: int, book: Book, source_dir: Path) -> bool:
        """Download a single part with retry logic."""
        assert isinstance(book, TextBook), f"Expected PdfBook, got {type(book).__name__}"

        part = book.parts[part_num]
        url = f"https://www.litres.ru{book.base_url}json/{part['url']}"
        filepath = source_dir / f"{part_num}.txt"

        try:
            response = self._fetch_with_retry(url, filepath)
            with filepath.open('w', encoding="utf-8") as f:
                f.write(response.text)
            return True
        except Exception as e:
            logger.error(f"Failed to download part {part_num}: {e}")
            return False


    def _extract_text(self, data: str | list | dict) -> str:
        """Recursively extracts text from nested data structures."""
        text = ""
        if isinstance(data, str):
            text = data
        elif isinstance(data, list):
            text = "".join(self._extract_text(item) for item in data)
        elif isinstance(data, dict):
            if "c" in data and data["c"] is not None:
                text = self._extract_text(data["c"])
        
        # Litres uses soft hyphens for word wrapping, remove them.
        return text.replace("\u00ad", "")