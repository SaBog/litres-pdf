import os
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from litres.config import settings
from litres.exceptions import BookProcessingError
from litres.utils import sanitize_filename


class OutFormat(Enum):
    PDF = 1
    TXT = 2
    FB2 = 3


class BookPipeline(ABC):
    def __init__(self, session):
        self.session = session
        self.book = None

    @property
    def input_dir(self):
        return Path(settings.source_dir)

    @property
    def output_dir(self):
        return Path(settings.books_dir)

    @property
    def filename(self):
        return sanitize_filename(self.book.meta.title) if self.book else ''

    @property
    def folders_info(self):
        return SaveFolderInfo(self)


    @abstractmethod
    def extract_meta(self, url: str) -> None:
        pass

    @abstractmethod
    def download_pages(self) -> None:
        self.validate_book()
        pass

    @abstractmethod
    def save_file(self) -> None:
        pass

    def validate_book(self):
        if not self.book or not self.book.meta:
            raise BookProcessingError("Book meta must be set before proceeding.")

class SaveFolderInfo:
    def __init__(self, book: BookPipeline):
        self.filename = book.filename
        self.input_path = Path(book.input_dir) / self.filename
        self.output_path = Path(book.output_dir) / self.filename
        os.makedirs(self.input_path, exist_ok=True)
        os.makedirs(book.output_dir, exist_ok=True)

