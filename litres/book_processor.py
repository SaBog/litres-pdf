
import re
from typing import List

import requests

from litres.commands.book_request import BookRequestCommand
from litres.exceptions import BookProcessingError
from litres.handlers.base import BaseUrlHandler, OutFormat
from litres.handlers.handler_url_audiobook import HandlerUrlAudiobook
from litres.handlers.handler_url_o3 import HandlerUrlO3
from litres.handlers.handler_url_o4 import HandlerUrlO4
from litres.handlers.handler_url_o5 import HandlerUrlO5
from litres.models.book import BookRequest


class BookProcessor:
    """Orchestrates the book processing workflow using BookPipeline subclasses."""

    def __init__(self, session: requests.Session):
        self._session = session

        self.handlers: List[BaseUrlHandler] = [
            HandlerUrlO3(session), 
            HandlerUrlO4(session), 
            HandlerUrlO5(session),
            HandlerUrlAudiobook(session),
        ]

    def _is_general_book_url(self, url: str) -> bool:
        # Пример: https://www.litres.ru/book/author/book-title-12345/
        return bool(re.match(r".*/book/.+-\d+/?$", url))

    def _create_book_request(self, url: str) -> BookRequest:
        if self._is_general_book_url(url):
            return BookRequestCommand(self._session).create(url)

        return BookRequest(url=url)

    def _select_handler(self, bq: BookRequest) -> BaseUrlHandler:
        for handler in self.handlers:
            if handler.supports(bq):
                return handler
        
        raise BookProcessingError(f"Unsupported URL format: {bq.url}")

    def process_book(self, url: str):
        """
        Process a single book URL through all stages using the appropriate pipeline.
        """
        book_req = self._create_book_request(url)
        handler = self._select_handler(book_req)

        handler.load(book_req)
        handler.save(out_format=[OutFormat.PDF, OutFormat.FB2, OutFormat.MP3]) 