from collections.abc import Mapping

from litres.book_request import BookRequestResolver
from litres.exceptions import BookProcessingError
from litres.handlers.book_handler import BookHandler
from litres.models.book import BookFormat, BookRequest
from litres.models.out_format import OutFormat


class BookProcessor:
    """Resolves a URL to a book format and runs the handler registered for it."""

    def __init__(
        self,
        request_resolver: BookRequestResolver,
        handlers: Mapping[BookFormat, BookHandler],
        out_format_priority: list[OutFormat],
    ):
        self._request_resolver = request_resolver
        self.handlers = handlers
        self._out_format_priority = out_format_priority

    def _select_handler(self, bq: BookRequest) -> BookHandler:
        try:
            return self.handlers[bq.format]
        except KeyError:
            raise BookProcessingError(
                f"No handler for book format '{bq.format}': {bq.url}"
            ) from None

    def process_book(self, url: str):
        """Process a single book URL through all stages using the matching handler."""
        book_req = self._request_resolver.resolve(url)
        handler = self._select_handler(book_req)

        handler.load(book_req)
        handler.save(self._out_format_priority)
