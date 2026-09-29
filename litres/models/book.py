from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, NotRequired, TypedDict, TypeVar


class BookFormat(StrEnum):
    """LitRes viewer format a book is served in."""

    O3 = "o3"  # page images
    O4 = "o4"  # structured text
    AUDIOBOOK = "audiobook"


@dataclass
class Author:
    """Класс для представления информации об авторе"""

    first: str
    middle: str | None = None
    last: str | None = None

    def full_name(self) -> str:
        """Возвращает полное имя автора"""
        parts = [self.first]
        if self.middle:
            parts.append(self.middle)
        if self.last:
            parts.append(self.last)
        return " ".join(parts)

    def __str__(self):
        return self.full_name()


@dataclass
class Page:
    """Класс для представления страницы книги"""

    width: int
    height: int
    extension: str


@dataclass
class BookMeta:
    """Класс для представления метаинформации о книге"""

    authors: list[Author]
    title: str
    version: float
    uuid: str


class TextPart(TypedDict):
    """A chapter entry of a text book table of contents; LitRes adds more keys."""

    url: str
    c: NotRequired[list]


class AudioPart(TypedDict):
    filename: str
    file_id: str
    url: str


PartT = TypeVar("PartT")


@dataclass
class Book(Generic[PartT]):
    meta: BookMeta
    parts: list[PartT]

    @property
    def total_parts(self) -> int:
        return len(self.parts)


@dataclass
class PdfBook(Book[Page]):
    file_id: str


@dataclass
class TextBook(Book[TextPart]):
    base_url: str


@dataclass
class AudioBook(Book[AudioPart]):
    art_id: str


@dataclass
class BookRequest:
    """What the user asked for, resolved to a format and the ids needed to fetch it."""

    url: str
    format: BookFormat
    file_id: str | None = None
    art_id: str | None = None
    base_url: str | None = None
