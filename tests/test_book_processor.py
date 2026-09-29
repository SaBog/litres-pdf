from unittest.mock import MagicMock

import pytest

from litres.book_processor import BookProcessor
from litres.book_request import BookRequestResolver
from litres.exceptions import BookProcessingError
from litres.models.book import BookFormat, BookRequest
from litres.models.out_format import OutFormat


def make_processor(handlers=None, resolver=None, priority=None):
    return BookProcessor(
        resolver or MagicMock(spec=BookRequestResolver),
        handlers or {},
        priority or [OutFormat.PDF],
    )


def test_select_handler_uses_request_format():
    o3, o4 = MagicMock(), MagicMock()
    bp = make_processor({BookFormat.O3: o3, BookFormat.O4: o4})

    assert bp._select_handler(BookRequest(url="u", format=BookFormat.O4)) is o4


def test_select_handler_without_registered_format_raises():
    bp = make_processor({BookFormat.O3: MagicMock()})
    with pytest.raises(BookProcessingError, match="No handler for book format"):
        bp._select_handler(BookRequest(url="u", format=BookFormat.AUDIOBOOK))


def test_process_book_resolves_url_then_loads_and_saves():
    resolver = MagicMock(spec=BookRequestResolver)
    request = BookRequest(url="https://viewer/x", format=BookFormat.O3)
    resolver.resolve.return_value = request
    handler = MagicMock()
    priority = [OutFormat.FB2, OutFormat.PDF]
    bp = make_processor({BookFormat.O3: handler}, resolver, priority)

    bp.process_book("https://user-typed/url")

    resolver.resolve.assert_called_once_with("https://user-typed/url")
    handler.load.assert_called_once_with(request)
    handler.save.assert_called_once_with(priority)


def test_process_book_does_not_load_when_format_has_no_handler():
    resolver = MagicMock(spec=BookRequestResolver)
    resolver.resolve.return_value = BookRequest(url="u", format=BookFormat.AUDIOBOOK)
    handler = MagicMock()
    bp = make_processor({BookFormat.O3: handler}, resolver)

    with pytest.raises(BookProcessingError):
        bp.process_book("u")
    handler.load.assert_not_called()
