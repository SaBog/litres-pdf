import os
from typing import List
import requests

from ..config import logger, settings
from ..models import Book
from ..utils import sanitize_filename, extract_file_id
from ..exceptions import BookProcessingError
from .api_client import LitresAPIClient
from .downloader import PageDownloader
from .pdf import PDFService

DEFAULT_MIN_FILE_SIZE = 1024

class BookProcessor:
    """Orchestrates the book processing workflow."""

    def __init__(self, session: requests.Session):
        self.api_client = LitresAPIClient(session)
        self.downloader = PageDownloader(session)
        self.pdf_service = PDFService(quality=settings.quality, dpi=settings.dpi)

    def process_book(self, url: str) -> None:
        """Process a single book URL through all stages."""
        file_id = extract_file_id(url)
        if not file_id:
            raise BookProcessingError(f"Failed to extract file_id from URL: {url}")

        book = self.api_client.get_book(file_id)
        
        image_dir = self._setup_image_directory(book)
        
        existing_pages = self._get_existing_pages(book, image_dir)
        
        self.downloader.download_pages(book, image_dir, existing_pages)

        final_check = self._get_existing_pages(book, image_dir)
        if len(final_check) != book.total_pages:
            missing = sorted(set(range(book.total_pages)) - set(final_check))
            logger.warning(f"Download incomplete. Missing pages: {missing}")
            raise BookProcessingError("Download failed, not all pages were retrieved.")

        logger.info(f"Book successfully saved to: {image_dir}")
        
        self._create_pdf(book, image_dir)

    def _setup_image_directory(self, book: Book) -> str:
        """Create and return the directory for storing book page images."""
        title = sanitize_filename(book.meta.title)
        image_dir = os.path.join(settings.image_dir, title)
        os.makedirs(image_dir, exist_ok=True)
        return image_dir

    def _get_existing_pages(self, book: Book, image_dir: str) -> List[int]:
        """Get a list of successfully downloaded page indices."""
        existing = []
        min_file_size = getattr(settings, 'min_file_size', DEFAULT_MIN_FILE_SIZE)
        
        if not os.path.exists(image_dir):
            return existing
            
        for index, page in enumerate(book.pages):
            filename = f"page_{index:04d}.{page.extension}"
            filepath = os.path.join(image_dir, filename)
            
            if os.path.exists(filepath) and os.path.getsize(filepath) > min_file_size:
                existing.append(index)
        return existing

    def _create_pdf(self, book: Book, image_dir: str) -> None:
        """Create the final PDF from the downloaded images."""
        output_pdf_filename = f"{sanitize_filename(book.meta.title)}.pdf"
        output_pdf_path = os.path.join(settings.pdf_dir, output_pdf_filename)
        
        os.makedirs(settings.pdf_dir, exist_ok=True)
        
        logger.info(f"Creating PDF: {output_pdf_path}")
        self.pdf_service.create_pdf(image_dir, output_pdf_path) 