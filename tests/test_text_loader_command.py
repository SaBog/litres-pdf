from unittest.mock import MagicMock, patch

import pytest

from litres.loaders.text_loader import TextLoaderCommand
from litres.models.book import TextBook


class DummyTextBook(TextBook):
    def __init__(self):
        self.base_url = "/base/"
        self.parts = [{"url": "part1"}]

@pytest.fixture
def text_book():
    return DummyTextBook()

def test_download_part_success(tmp_path, text_book):
    loader = TextLoaderCommand(MagicMock())
    part_num = 0
    source_dir = tmp_path
    book = text_book
    response = MagicMock()
    response.text = "hello"
    with patch.object(loader, "_fetch_with_retry", return_value=response):
        result = loader._download_part(part_num, book, source_dir)
        assert result
        assert (tmp_path / "0.txt").read_text() == "hello"

def test_download_part_error(tmp_path, text_book):
    loader = TextLoaderCommand(MagicMock())
    part_num = 0
    source_dir = tmp_path
    book = text_book
    with patch.object(loader, "_fetch_with_retry", side_effect=Exception("fail")), \
         patch("litres.loaders.text_loader.logger.error") as log_error:
        result = loader._download_part(part_num, book, source_dir)
        assert not result
        log_error.assert_called()

def test_download_part_wrong_type(tmp_path):
    loader = TextLoaderCommand(MagicMock())
    part_num = 0
    source_dir = tmp_path
    class NotTextBook:
        parts = [{"url": "part1"}]
    with pytest.raises(AttributeError):
        loader._download_part(part_num, NotTextBook(), source_dir)  # type: ignore 
