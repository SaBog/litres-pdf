import time
from collections.abc import Callable
from typing import TypeVar

import requests

from litres.config import logger
from litres.exceptions import BookProcessingError
from litres.loaders.base_loader import BaseLoader, retry_after_seconds
from litres.models.book import Book
from litres.services.litres_api import LitresApi

MAX_ATTEMPTS = 3

T = TypeVar("T", bound=Book)


class ReaderLoader(BaseLoader[T]):
    """Base for loaders that fetch files through the API's short-lived signed links."""

    def __init__(self, api: LitresApi, delay: float = 0.0, max_workers: int = 4):
        super().__init__(api.session, delay, max_workers)
        self._api = api

    def _fetch_signed(self, get_link: Callable[[], str]) -> requests.Response:
        """Request a link and download it, retrying with a fresh link and signature.

        Links and DRM signatures expire, so every retry asks for new ones; a 429
        pauses all workers. Raises BookProcessingError once attempts run out.
        """
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(0.5 * attempt)
                self._api.reset_drm()
            try:
                self._rate_limiter.wait(self._delay)
                return self._api.download(get_link())
            except requests.HTTPError as e:
                last_error = e
                if e.response is not None and e.response.status_code == 429:
                    pause = retry_after_seconds(e.response)
                    self._rate_limiter.penalize(pause)
                    logger.warning(f"429 Too Many Requests: pausing {pause} seconds")
            except (requests.RequestException, BookProcessingError) as e:
                last_error = e
        raise BookProcessingError(
            f"Giving up after {MAX_ATTEMPTS} attempts: {last_error!s}"
        ) from last_error
