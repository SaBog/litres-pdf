from venv import logger

from litres.exceptions import BookProcessingError
from litres.services.api_client import LitresAPIClient
from litres.services.loaders.text_loader import TextLoader
from litres.services.pipelines.processors.base import TextProcessor
from .base import BookPipeline, OutFormat
from .processors.registry import PROCESSOR_REGISTRY

class TextBookPipeline(BookPipeline):
    def __init__(self, session, output_type=OutFormat.TXT):
        super().__init__(session)
        self.output_type = output_type

    def extract_meta(self, url: str) -> None:
        self.book = LitresAPIClient(self.session).get_o4_book(url)
        logger.info(f"Successfully fetched book meta. Title: {self.book.meta.title}")

    def download_pages(self) -> None:
        self.validate_book()
        TextLoader(self.session).download_parts(self.book, self.folders_info)

    def save_file(self) -> None:
        fi = self.folders_info
        processor = PROCESSOR_REGISTRY.get(self.output_type)
        
        if not processor or not isinstance(processor, TextProcessor):
            raise BookProcessingError(f"Output type {self.output_type} not supported by this pipeline.")
        
        result_text = processor.process(fi.input_path, self.book)
        out_filename = f"{fi.output_path}.{processor.file_extension}"
        
        with open(out_filename, 'w', encoding='utf-8', buffering=1024*1024) as outfile:
            outfile.write(result_text)
        
        logger.info(f"Book text successfully saved to: {out_filename}") 