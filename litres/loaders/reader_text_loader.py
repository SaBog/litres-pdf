from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from tqdm import tqdm

from litres.config import logger
from litres.constants import SOURCE_IMAGE_FOLDER
from litres.exceptions import BookProcessingError
from litres.loaders.reader_loader import ReaderLoader
from litres.models.book import TextBook
from litres.models.book_paths import BookPaths
from litres.parsing import image_names


class ReaderTextLoader(ReaderLoader[TextBook]):
    """Downloads text parts and their images (text reader)."""

    def download_parts(self, book: TextBook, path: BookPaths) -> None:
        super().download_parts(book, path)
        self._fetch_missing_images(book, path.source)

    def _fetch_missing_images(self, book: TextBook, source_dir: Path) -> None:
        """A finished part counts as downloaded, so images that failed earlier (or
        that an older run never fetched) are picked up here."""
        if not book.file_id:
            return
        save_dir = source_dir / SOURCE_IMAGE_FOLDER

        missing: list[str] = []
        for part_num in range(book.total_parts):
            part_file = source_dir / f"{part_num}.txt"
            if not part_file.exists():
                continue
            for name in image_names(part_file.read_text(encoding="utf-8")):
                if name not in missing and not (save_dir / name).exists():
                    missing.append(name)
        if not missing:
            return

        logger.info(f"Downloading {len(missing)} missing images")
        save_dir.mkdir(parents=True, exist_ok=True)
        with (
            ThreadPoolExecutor(max_workers=self._max_workers) as executor,
            tqdm(
                total=len(missing),
                unit="img",
                desc="Images",
                ncols=100,
                colour="green",
            ) as pbar,
        ):
            for _ in executor.map(
                lambda name: self._download_image(book, name, save_dir), missing
            ):
                pbar.update(1)

    def _download_part(self, part_num: int, book: TextBook, source_dir: Path) -> bool:
        file_id = book.file_id
        if not file_id:
            logger.error(f"Failed to download part {part_num}: book has no file_id")
            return False

        resource = book.parts[part_num]["url"]
        try:
            response = self._fetch_signed(
                lambda: self._api.resource_link(file_id, resource, book.art_id)
            )
            try:
                # The server sends no charset; the web reader reads UTF-8
                text = response.content.decode("utf-8")
            finally:
                response.close()

            # Images first: the part file marks the part as done, so it must appear last
            self._download_images(text, book, source_dir / SOURCE_IMAGE_FOLDER)
            self._atomic_write(source_dir / f"{part_num}.txt", [text.encode("utf-8")])
            return True
        except (BookProcessingError, UnicodeDecodeError) as e:
            logger.error(f"Failed to download part {part_num}: {e!s}")
            return False

    def _download_images(self, part_text: str, book: TextBook, save_dir: Path) -> None:
        names = image_names(part_text)
        if not names or not book.file_id:
            return
        save_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            self._download_image(book, name, save_dir)

    def _download_image(self, book: TextBook, name: str, save_dir: Path) -> None:
        path = save_dir / name
        if path.exists():
            return
        try:
            self._save_response(self._fetch_image(book, name), path)
            logger.debug(f"Downloaded image: {name}")
        except BookProcessingError as e:
            logger.warning(f"Failed to download image {name}: {e!s}")

    def _fetch_image(self, book: TextBook, name: str) -> requests.Response:
        """Try the json/ path the reader still serves images from, then a signed link."""
        file_id = book.file_id
        assert file_id  # checked by the callers
        if book.art_id:
            try:
                self._rate_limiter.wait(self._delay)
                response = self._api.legacy_asset(book.art_id, file_id, name)
            except requests.RequestException as e:
                logger.debug(f"json/ path failed for {name} ({e!s}), trying a signed link")
            else:
                if response.headers.get("Content-Type", "").startswith("image/"):
                    return response
                # e.g. a login or error page served with a 200
                response.close()
                logger.debug(f"json/ path gave a non-image for {name}, trying a signed link")
        return self._fetch_signed(
            lambda: self._api.resource_link(file_id, name, book.art_id)
        )
