import os
import re
from pathlib import Path

from litres.config import logger
from litres.constants import SOURCE_IMAGE_FOLDER
from litres.loaders.base_loader import BaseLoader
from litres.models.book import TextBook


class TextLoader(BaseLoader[TextBook]):
    IMAGE_URL_TEMPLATE = "https://www.litres.ru{base_url}json/{img_name}"
    PART_URL_TEMPLATE = "https://www.litres.ru{base_url}json/{part_url}"

    def _download_part(self, part_num: int, book: TextBook, source_dir: Path) -> bool:
        """Download a single part with retry logic and download images if present."""
        part = book.parts[part_num]
        url = self.PART_URL_TEMPLATE.format(
            base_url=book.base_url, part_url=part["url"]
        )
        filepath = source_dir / f"{part_num}.txt"

        try:
            response = self._fetch_with_retry(url)
            try:
                text = response.text
            finally:
                response.close()
            # Images first: the part file marks the part as done, so it must appear last
            self._download_images_from_text(
                text, book.base_url, source_dir / SOURCE_IMAGE_FOLDER
            )
            self._atomic_write(filepath, [text.encode("utf-8")])
            return True
        except Exception as e:
            logger.error(f"Failed to download part {part_num}: {e}")
            return False

    def _download_images_from_text(self, part_text: str, base_url: str, save_dir: Path):
        """Find all image filenames by regexp and download them."""
        image_names = set(re.findall(r"i_\d+\.\w+", part_text))

        if image_names:
            os.makedirs(save_dir, exist_ok=True)

        for img_name in image_names:
            self._download_image(base_url, img_name, save_dir)

    def _download_image(self, base_url: str, img_name: str, save_dir: Path):
        """Download a single image by name to the save_dir, if not already exists."""
        img_path = save_dir / img_name

        if img_path.exists():
            return

        url = self.IMAGE_URL_TEMPLATE.format(base_url=base_url, img_name=img_name)
        try:
            response = self.fetch(url, delay=self._delay)
            self._save_response(response, img_path)
            logger.debug(f"Downloaded image: {img_name}")
        except Exception as e:
            logger.warning(f"Failed to download image {img_name}: {e}")
