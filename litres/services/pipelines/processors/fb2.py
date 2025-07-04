from pathlib import Path
from litres.models.book import TextBook
from litres.services.pipelines.base import OutFormat
from .base import TextProcessor

class Fb2Processor(TextProcessor):
    output_type = OutFormat.FB2
    @property
    def file_extension(self) -> str:
        return 'fb2'
    def process(self, source_dir: Path, book: TextBook) -> str:
        # TODO: Реализовать FB2 конвертацию
        raise NotImplementedError("FB2 conversion is not implemented yet.")