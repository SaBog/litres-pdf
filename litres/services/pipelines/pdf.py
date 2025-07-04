from litres.config import settings, logger
from litres.services.api_client import LitresAPIClient
from litres.services.loaders.pdf_loader import PdfLoader
from litres.services.pdf import PDFService
from .base import BookPipeline

class PDFBookPipeline(BookPipeline):
    def extract_meta(self, url: str) -> None:
        self.book = LitresAPIClient(self.session).get_o3_book(url)
        logger.info(f"Successfully fetched book meta. Title: {self.book.meta.title}")

    def download_pages(self) -> None:
        self.validate_book()
        PdfLoader(self.session).download_parts(self.book, self.folders_info)

    def save_file(self) -> None:
        fi = self.folders_info
        pdf_service = PDFService(quality=settings.quality, dpi=settings.dpi)
        output_filename = str(fi.output_path) + '.pdf'
        pdf_service.create_pdf(str(fi.input_path), output_filename)

        logger.info(f"Book PDF successfully saved to: {fi.output_path}") 