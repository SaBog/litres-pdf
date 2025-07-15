from litres.commands.extract_o4_book import ExtractO4BookCommand
from litres.config import logger
from litres.engines.o4_2_fb2 import O4ToFB2Engine
from litres.engines.o4_2_pdf import O4ToPDFEngine
from litres.engines.o4_2_txt import O4ToTXTEngine
from litres.loaders.text_loader import TextLoaderCommand
from litres.models.book import BookRequest
from litres.handlers.base import BaseUrlHandler


class HandlerUrlO4(BaseUrlHandler):
    engines = [
        O4ToPDFEngine(),
        O4ToFB2Engine(),
        O4ToTXTEngine(),
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

