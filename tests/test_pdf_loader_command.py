from unittest.mock import MagicMock, patch

import pytest

from litres.loaders.pdf_loader import ImgLoaderCommand
from litres.models.book import Page, PdfBook


class DummyPdfBook(PdfBook):
    def __init__(self):
        self.file_id = "fid"
        self.parts = [Page(width=100, height=200, extension="pdf")]

@pytest.fixture
def pdf_book():
    return DummyPdfBook()

def test_download_part_success(tmp_path, pdf_book):
    loader = ImgLoaderCommand(MagicMock())
    part_num = 0
    source_dir = tmp_path
    book = pdf_book
    response = MagicMock()
    response.iter_content.return_value = [b"data"]
    with patch.object(loader, "_fetch_with_retry", return_value=response):
        result = loader._download_part(part_num, book, source_dir)
        assert result
        assert (tmp_path / "0.pdf").exists()

def test_download_part_error(tmp_path, pdf_book):
    loader = ImgLoaderCommand(MagicMock())
    part_num = 0
    source_dir = tmp_path
    book = pdf_book
    with patch.object(loader, "_fetch_with_retry", side_effect=Exception("fail")), \
         patch("litres.loaders.pdf_loader.logger.error") as log_error:
        result = loader._download_part(part_num, book, source_dir)
        assert not result
        log_error.assert_called()

def test_download_part_wrong_type(tmp_path):
    loader = ImgLoaderCommand(MagicMock())
    part_num = 0
    source_dir = tmp_path
    class NotPdfBook:
        parts = [MagicMock(width=100, height=200, extension="pdf")]
    with pytest.raises(AttributeError):
        loader._download_part(part_num, NotPdfBook(), source_dir)  # type: ignore 