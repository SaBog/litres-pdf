import pytest
from unittest.mock import MagicMock
import requests

from litres.services.api_client import LitresAPIClient
from litres.models import Book
from litres.exceptions import BookProcessingError

RAW_API_RESPONSE = r"""
PFURL.pdf[109410952] = {
Meta: {"Authors":[],"version":"","UUID":"11238d05-59ac-11ef-8ce3-0cc47af30fe4","Title":"Burda №08/2024"},
pages: [{p:[{ w: 1900, h: 2416, ext: 'jpg'},{ w: 1900, h: 2416, ext: 'jpg'}]}]
};
"""

@pytest.fixture
def mock_session():
    """Fixture to create a mock requests.Session."""
    mock = MagicMock(spec=requests.Session)
    mock.get.return_value.text = RAW_API_RESPONSE
    mock.get.return_value.status_code = 200
    mock.get.return_value.raise_for_status.return_value = None
    return mock

def test_get_book_success(mock_session):
    """Test successful book data retrieval and parsing."""
    client = LitresAPIClient(session=mock_session)
    book = client.get_book("109410952")

    assert isinstance(book, Book)
    assert book.file_id == "109410952"
    assert book.meta.title == "Burda №08/2024"
    assert len(book.pages) == 2
    assert book.pages[0].width == 1900

def test_get_book_bad_response(mock_session):
    """Test handling of a bad or unexpected API response."""
    mock_session.get.return_value.text = "This is not a valid response"
    client = LitresAPIClient(session=mock_session)
    
    with pytest.raises(BookProcessingError, match="Could not find file_id in response"):
        client.get_book("123")

def test_get_book_http_error(mock_session):
    """Test that an HTTP error raises a BookProcessingError."""
    mock_session.get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
    client = LitresAPIClient(session=mock_session)

    with pytest.raises(BookProcessingError):
        client.get_book("123") 