import pytest

from litres.exceptions import BookProcessingError


def test_book_processing_error():
    with pytest.raises(BookProcessingError):
        raise BookProcessingError("error") 