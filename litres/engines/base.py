from enum import Enum
from litres.models.output_path_handler import OutputPathHandler

from abc import abstractmethod
from typing import List


class OutFormat(Enum):
    TXT = "txt"
    IMG = "img"
    FB2 = "fb2"
    PDF = "pdf"


class Engine:
    SUPPORTED_OUT_FORMAT: OutFormat

    @abstractmethod
    def execute(self, path: OutputPathHandler):
        pass

    def supports(self, out_formats: List[OutFormat]) -> bool:
        if not any(fmt == self.SUPPORTED_OUT_FORMAT for fmt in out_formats):
            return False
        return True
