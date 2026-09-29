from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from litres.models.book import Book
from litres.models.book_paths import BookPaths
from litres.models.out_format import OutFormat

BookT = TypeVar("BookT", bound=Book)


class Engine(ABC, Generic[BookT]):
    SUPPORTED_OUT_FORMAT: OutFormat

    @abstractmethod
    def execute(self, book: BookT, path: BookPaths) -> None:
        pass

    def supports(self, out_format: OutFormat) -> bool:
        return out_format == self.SUPPORTED_OUT_FORMAT
