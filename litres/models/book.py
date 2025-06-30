import re
from dataclasses import dataclass
from typing import List, Optional
import json

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
    
    def primary_author(self) -> Optional[Author]:
        """Возвращает первого автора"""
        return self.authors[0] if self.authors else None
    
    def __str__(self):
        authors_str = ", ".join(str(author) for author in self.authors)
        return f'"{self.title}" by {authors_str} (v{self.version})'
    
@dataclass
class Book:
    """Главный класс для представления книги"""
    file_id: str
    meta: BookMeta
    pages: List[Page]
    
    @property
    def total_pages(self) -> int:
        return len(self.pages) 