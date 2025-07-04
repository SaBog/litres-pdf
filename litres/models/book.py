from dataclasses import dataclass
from typing import List, Optional, Any

@dataclass
class Author:
    """Класс для представления информации об авторе"""
    first: str
    middle: Optional[str] = None
    last: Optional[str] = None
    
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
    authors: List[Author]
    title: str
    version: float
    uuid: str
    
@dataclass
class Book:
    meta: BookMeta
    parts: List[Any]
    
    @property
    def total_parts(self) -> int:
        return len(self.parts)

@dataclass
class PdfBook(Book):
    file_id: str
    parts: List[Page]


@dataclass
class TextBook(Book):
    base_url: str