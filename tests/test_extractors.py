from unittest.mock import MagicMock

import pytest

from litres.exceptions import BookProcessingError
from litres.extractors.o3 import O3Extractor
from litres.extractors.o4 import O4Extractor
from litres.models.book import BookFormat, BookRequest


def test_o3_extractor_requires_file_id_from_request():
    session = MagicMock()
    bq = BookRequest(url="https://x/or.html?art=5", format=BookFormat.O3)
    with pytest.raises(BookProcessingError, match="file_id"):
        O3Extractor(session).get(bq)
    session.get.assert_not_called()


def test_o4_extractor_requires_base_url_from_request():
    session = MagicMock()
    bq = BookRequest(url="https://x/or.html", format=BookFormat.O4)
    with pytest.raises(BookProcessingError, match="base_url"):
        O4Extractor(session).get(bq)
    session.get.assert_not_called()


def test_o3_extractor_fetches_by_file_id():
    session = MagicMock()
    session.get.return_value.text = "x"
    bq = BookRequest(url="u", format=BookFormat.O3, file_id="123")
    with pytest.raises(BookProcessingError):  # body is not a valid book description
        O3Extractor(session).get(bq)
    assert session.get.call_args.args[0].endswith("get_pdf_js/?file=123")
