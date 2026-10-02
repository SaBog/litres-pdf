from collections.abc import Sequence
from pathlib import Path
from typing import Generic, Protocol, TypeVar

from litres.config import logger
from litres.engines.base import BookT, Engine
from litres.exceptions import BookProcessingError
from litres.models.book import BookRequest
from litres.models.book_paths import BookPaths
from litres.models.out_format import OutFormat
from litres.utils import sanitize_filename

BookT_co = TypeVar("BookT_co", covariant=True)
BookT_contra = TypeVar("BookT_contra", contravariant=True)


class BookExtractor(Protocol[BookT_co]):
    """Fetches book metadata for a request."""

    def get(self, bq: BookRequest) -> BookT_co: ...


class BookLoader(Protocol[BookT_contra]):
    """Downloads the parts of a book into the source directory."""

    def download_parts(self, book: BookT_contra, path: BookPaths) -> None: ...

    def download_extras(self, book: BookT_contra, path: BookPaths) -> None: ...


class BookHandler(Generic[BookT]):
    """Loads one kind of book and saves it with the first matching engine."""

    def __init__(
        self,
        extractor: BookExtractor[BookT],
        loader: BookLoader[BookT],
        engines: Sequence[Engine[BookT]],
        source_dir: Path,
        books_dir: Path,
    ):
        self._extractor = extractor
        self._loader = loader
        self._engines = engines
        self._source_dir = source_dir
        self._books_dir = books_dir
        self.book: BookT

    def _paths_for_book(self) -> BookPaths:
        filename = sanitize_filename(self.book.meta.title)
        return BookPaths(
            filename=filename,
            source=self._source_dir / filename,
            output=self._books_dir,
        )

    def load(self, bq: BookRequest) -> None:
        self.book = self._extractor.get(bq)
        logger.info(f"Fetched book meta. Title: {self.book.meta.title}")

        paths = self._paths_for_book()
        paths.makedirs()
        self._loader.download_parts(self.book, paths)
        self._loader.download_extras(self.book, paths)

    def save(self, out_format_priority: list[OutFormat]) -> None:
        engine = self._select_engine(out_format_priority)
        logger.debug(f"Using engine: {engine}")

        paths = self._paths_for_book()
        paths.makedirs()
        engine.execute(self.book, paths)
        logger.info(f"File: {paths.filename} saved")

    def _select_engine(self, out_format_priority: list[OutFormat]) -> Engine[BookT]:
        for preferred_format in out_format_priority:
            for engine in self._engines:
                if engine.supports(preferred_format):
                    logger.debug(
                        f"Found engine for preferred format: {preferred_format}"
                    )
                    return engine
        raise BookProcessingError(
            "No available engine found for any of the preferred formats"
        )
