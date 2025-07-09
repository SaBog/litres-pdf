from litres.handlers.base import BaseUrlHandler
from litres.models.book import BookRequest


class HandlerUrlO5(BaseUrlHandler):
    def supports(self, bq: BookRequest) -> bool:
        return False

    def load(self, bq: BookRequest):
        # do something
        pass
