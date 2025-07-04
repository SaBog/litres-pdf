from abc import ABC, abstractmethod
from pathlib import Path
from litres.services.pipelines.base import OutFormat
from litres.models.book import TextBook

class TextProcessor(ABC):
    output_type: OutFormat

    @property
    @abstractmethod
    def file_extension(self) -> str:
        pass

    @abstractmethod
    def process(self, source_dir: Path, book: TextBook) -> str:
        """Обрабатывает папку с частями и возвращает итоговый текст в нужном формате"""
        pass 