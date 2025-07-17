from litres.commands.extract_o3_book import ExtractO3BookCommand
from litres.config import app_settings, logger
from litres.engines.o3.pdf_engine import IMG2PDFEngine
from litres.handlers.base import BaseUrlHandler
from litres.loaders.pdf_loader import ImgLoaderCommand
from litres.models.book import BookRequest


class HandlerUrlO3(BaseUrlHandler):
    engines = [
        IMG2PDFEngine(
            quality=app_settings.quality, 
            dpi=app_settings.dpi,
        )
    ]

    def supports(self, bq: BookRequest) -> bool:
        return (
            '/static/or3/view/or.html' in bq.url and
            'file=' in bq.url
        )

    def load(self, bq: BookRequest):
        self.book = ExtractO3BookCommand(self._session).get(bq)
        logger.info(f"Successfully fetched book meta. Title: {self.book.meta.title}")
        ImgLoaderCommand(self._session).download_parts(self.book, self.path_handler)
