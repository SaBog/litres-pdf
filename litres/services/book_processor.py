from litres.exceptions import BookProcessingError
from litres.services.pipelines.text import TextBookPipeline
from litres.services.pipelines.pdf import PDFBookPipeline

class BookProcessor:
    """Orchestrates the book processing workflow using BookPipeline subclasses."""

    def __init__(self, session):
        self._session = session

    def process_book(self, url: str):
        """
        Process a single book URL through all stages using the appropriate pipeline.
        """
        if "/static/or4/view/or.html" in url:
            pipeline = TextBookPipeline(self._session)
        elif "/static/or3/view/or.html" in url:
            pipeline = PDFBookPipeline(self._session)
        else:
            raise BookProcessingError(f"Unsupported URL format: {url}")

        pipeline.extract_meta(url)
        pipeline.download_pages()
        pipeline.save_file() 