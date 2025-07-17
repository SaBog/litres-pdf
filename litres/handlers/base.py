from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

import requests

from litres.config import app_settings, logger
from litres.engines.base import Engine, OutFormat
from litres.exceptions import BookProcessingError
from litres.models.book import Book, BookRequest
from litres.models.output_path_handler import OutputPathHandler
from litres.utils import sanitize_filename


class BaseUrlHandler(ABC):
    engines: List[Engine] =[]

    def __init__(self, session: requests.Session):
        self._session = session
        self.book: Book

    @property
    def path_handler(self) -> OutputPathHandler:
        filename = sanitize_filename(self.book.meta.title)
        return OutputPathHandler(
            filename=filename,
            source=Path(app_settings.source_dir) / filename,
            output=Path(app_settings.books_dir)
        )
    
    @abstractmethod
    def supports(self, bq: BookRequest) -> bool:
        pass

    @abstractmethod
    def load(self, bq: BookRequest):
        pass

    def save(self, out_format_priority: List[OutFormat]):
        engine = self._select_engine(out_format_priority)
        logger.debug(f'Using engine: {engine}')
        
        engine.execute(self.book, self.path_handler)
        logger.info(f'File: {self.path_handler.filename} saved')

    def _select_engine(self, out_format_priority: List[OutFormat]):
        for preferred_format in out_format_priority:
            for engine in self.engines:
                if engine.supports([preferred_format]):
                    logger.debug(f'Found engine for preferred format: {preferred_format}')
                    return engine
        raise BookProcessingError("No available engine found for any of the preferred formats")
