from abc import abstractmethod
from enum import Enum
from typing import List

from litres.models.book import Book
from litres.models.output_path_handler import OutputPathHandler


class OutFormat(Enum):
    TXT = "txt"
    IMG = "img"
    FB2 = "fb2"
    PDF = "pdf"
    MP3 = "mp3"


class Engine:
    SUPPORTED_OUT_FORMAT: OutFormat

    @abstractmethod
    def execute(self, book: Book, path: OutputPathHandler):
        pass

    def supports(self, out_formats: List[OutFormat]) -> bool:
        if not any(fmt == self.SUPPORTED_OUT_FORMAT for fmt in out_formats):
            return False
        return True
