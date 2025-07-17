from litres.commands.extract_o4_book import ExtractO4BookCommand
from litres.config import logger
from litres.engines.o4.fb2_engine import FB2Engine
from litres.engines.o4.pdf_engine import PDFEngine
from litres.engines.o4.txt_engine import TXTEngine
from litres.handlers.base import BaseUrlHandler
from litres.loaders.text_loader import TextLoaderCommand
from litres.models.book import BookRequest


class HandlerUrlO4(BaseUrlHandler):
    engines = [
        PDFEngine(),
        FB2Engine(),
        TXTEngine(),
    ]

    def supports(self, bq: BookRequest) -> bool:
        return (
            '/static/or4/view/or.html' in bq.url and
            'baseurl=' in bq.url
        )

    def load(self, bq: BookRequest):
        self.book = ExtractO4BookCommand(self._session).get(bq)
        logger.info(f"Fetched book meta. Title:{self.book.meta.title}")
        TextLoaderCommand(self._session).download_parts(self.book, self.path_handler)

