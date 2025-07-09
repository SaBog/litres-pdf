import pytest
from unittest.mock import MagicMock, patch
from litres.book_processor import BookProcessor
from litres.models.book import BookRequest

@patch("litres.book_processor.BaseUrlHandler")
@patch("litres.book_processor.BookRequestCommand.create", return_value=BookRequest(url="https://www.litres.ru/book/author/book-title-12345/"))
def test_is_general_book_url_and_create_book_request(mock_create, mock_handler):
    session = MagicMock()
    bp = BookProcessor(session)
    # Use a URL that matches the regex in _is_general_book_url
    assert bp._is_general_book_url("https://www.litres.ru/book/author/book-title-12345/") is True
    assert bp._is_general_book_url("https://other.ru/book/123/") is False
    assert bp._create_book_request("https://www.litres.ru/book/author/book-title-12345/").url == "https://www.litres.ru/book/author/book-title-12345/"

@patch("litres.book_processor.BookProcessor._select_handler")
@patch("litres.book_processor.BookProcessor._create_book_request")
def test_process_book(mock_create_bq, mock_select_handler):
    session = MagicMock()
    bp = BookProcessor(session)
    mock_create_bq.return_value = MagicMock()
    handler = MagicMock()
    mock_select_handler.return_value = handler
    bp.process_book("https://www.litres.ru/book/author/book-title-12345/")
    handler.load.assert_called() 