import time
import requests

from tqdm import tqdm
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, TypeVar, Generic

from litres.config import app_settings, logger
from litres.exceptions import BookProcessingError
from litres.models.book import Book
from litres.models.output_path_handler import OutputPathHandler
from litres.utils import timing

MAX_WORKERS = 8

T = TypeVar('T', bound=Book)

class BaseLoaderCommand(Generic[T]):
    """Handles downloading book parts with retry logic and progress tracking."""

    def __init__(self, session: requests.Session):
        self._session = session

    def look_for_loaded_content(self, source_dir: Path, except_filename: Optional[str] = None) -> List[int]:
        return sorted(
            int(f.stem)
            for f in source_dir.glob("*")
            if f.name != except_filename and f.stem.isdigit()
        )

    @timing
    def download_parts(self, book: T, path: OutputPathHandler) -> None:
        """Download all missing parts for a book."""
        existing_parts = self.look_for_loaded_content(path.source)
        expected_parts = set(range(book.total_parts))
        parts_to_download = sorted(expected_parts - set(existing_parts))

        if not parts_to_download:
            logger.info("All parts are already downloaded.")
            return
        
        overall_success = True

        with tqdm(
            total=len(parts_to_download),
            unit='part',
            desc="Downloading",
            ncols=100,
            colour='green'
        ) as pbar, ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

            futures = {
                executor.submit(self._download_part, part_num, book, path.source): part_num
                for part_num in parts_to_download
            }

            for future in as_completed(futures):
                part_num = futures[future]
                try:
                    success = future.result()
                    if not success:
                        overall_success = False
                        logger.error(f"Download failed for part {part_num}")
                except Exception as e:
                    logger.error(f"Exception while downloading part {part_num}: {e}")
                finally:
                    pbar.update(1)

        # Проверка, что все страницы скачаны
        downloaded_parts = set(self.look_for_loaded_content(path.source))
        missing_parts = expected_parts - downloaded_parts

        if not overall_success or missing_parts:
            raise BookProcessingError(f"Missing or corrupted parts after download: {sorted(missing_parts)}")
        
        logger.info(f"Book successfully saved to: {path.source}")
        
    def _download_part(self, part_num: int, book: T, source_dir: Path) -> bool:
        raise NotImplementedError(f'_download_part require implementation')
    
    def _fetch_with_retry(self, url: str, filepath: Path, max_attempts: int = 2) -> requests.Response:
        """Try to fetch a file with retries and rate limiting handling."""
        attempt = 0
        delay = app_settings.delay
        while attempt < max_attempts:
            attempt += 1
            try:
                return self.fetch(url, delay=delay)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code != 429:
                    raise
                delay = int(e.response.headers.get("Retry-After", 15))
                logger.warning(f"429 Too Many Requests: waiting {delay} seconds")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error during fetch: {e}")
        raise RuntimeError(f"Failed to fetch {url} after {max_attempts} attempts")

    def fetch(self, url: str, delay: float = 0) -> requests.Response:
        """Download and write content from URL to file."""
        if (delay > 0):
            time.sleep(delay)
        
        response = self._session.get(url, stream=True, timeout=30)
        response.raise_for_status()
        return response