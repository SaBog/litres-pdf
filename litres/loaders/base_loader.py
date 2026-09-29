import os
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Generic, TypeVar

import requests
from tqdm import tqdm

from litres.config import logger
from litres.exceptions import BookProcessingError
from litres.models.book import Book
from litres.models.book_paths import BookPaths
from litres.utils import timing

DEFAULT_RETRY_AFTER = 15

T = TypeVar("T", bound=Book)


class RateLimiter:
    """Spaces request starts across threads and lets a 429 pause all of them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self, interval: float) -> None:
        if interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_slot)
            self._next_slot = start + interval
        if start > now:
            time.sleep(start - now)

    def penalize(self, seconds: float) -> None:
        with self._lock:
            self._next_slot = max(self._next_slot, time.monotonic() + seconds)


def _retry_after_seconds(response: requests.Response) -> float:
    try:
        return max(float(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER)), 0)
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER


class BaseLoader(ABC, Generic[T]):
    """Handles downloading book parts with retry logic and progress tracking."""

    def __init__(
        self,
        session: requests.Session,
        delay: float = 0.0,
        max_workers: int = 4,
    ):
        self._session = session
        self._delay = delay
        self._max_workers = max_workers
        self._rate_limiter = RateLimiter()

    def look_for_loaded_content(self, source_dir: Path) -> list[int]:
        return sorted(int(f.stem) for f in source_dir.glob("*") if f.stem.isdigit())

    @timing
    def download_parts(self, book: T, path: BookPaths) -> None:
        """Download all missing parts for a book."""
        existing_parts = self.look_for_loaded_content(path.source)
        expected_parts = set(range(book.total_parts))
        parts_to_download = sorted(expected_parts - set(existing_parts))

        if not parts_to_download:
            logger.info("All parts are already downloaded.")
            return

        overall_success = True

        with (
            tqdm(
                total=len(parts_to_download),
                unit="part",
                desc="Downloading",
                ncols=100,
                colour="green",
            ) as pbar,
            ThreadPoolExecutor(max_workers=self._max_workers) as executor,
        ):
            futures = {
                executor.submit(
                    self._download_part, part_num, book, path.source
                ): part_num
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
            raise BookProcessingError(
                f"Missing or corrupted parts after download: {sorted(missing_parts)}"
            )

        logger.info(f"Book successfully saved to: {path.source}")

    @abstractmethod
    def _download_part(self, part_num: int, book: T, source_dir: Path) -> bool:
        """Download one part into source_dir; return True on success."""

    @staticmethod
    def _atomic_write(filepath: Path, chunks: Iterable[bytes]) -> None:
        """Write to a temp file and rename, so a partial file never looks complete."""
        tmp = filepath.with_name(
            f"{filepath.name}.{os.getpid()}.{threading.get_ident()}.part"
        )
        try:
            with tmp.open("wb") as f:
                for chunk in chunks:
                    f.write(chunk)
            os.replace(tmp, filepath)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def _save_response(
        self, response: requests.Response, filepath: Path, chunk_size: int = 8192
    ) -> None:
        """Stream the response body into filepath atomically and close the response."""
        try:
            self._atomic_write(filepath, response.iter_content(chunk_size))
        finally:
            response.close()

    def _fetch_with_retry(self, url: str, max_attempts: int = 2) -> requests.Response:
        """Try to fetch a file with retries and rate limiting handling."""
        attempt = 0
        delay = self._delay
        while attempt < max_attempts:
            attempt += 1
            try:
                return self.fetch(url, delay=delay)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code != 429:
                    raise
                retry_after = _retry_after_seconds(e.response)
                self._rate_limiter.penalize(retry_after)
                logger.warning(f"429 Too Many Requests: pausing {retry_after} seconds")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error during fetch: {e}")
        raise RuntimeError(f"Failed to fetch {url} after {max_attempts} attempts")

    def fetch(self, url: str, delay: float = 0) -> requests.Response:
        """Download and write content from URL to file."""
        self._rate_limiter.wait(delay)

        response = self._session.get(url, stream=True, timeout=30)
        response.raise_for_status()
        return response
