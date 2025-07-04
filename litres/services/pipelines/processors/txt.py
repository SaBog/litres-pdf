import json
from pathlib import Path
from litres.models.book import TextBook
from litres.services.pipelines.base import OutFormat
from venv import logger
from .base import TextProcessor
from litres.utils import key_re, comma_re

class TxtProcessor(TextProcessor):
    output_type = OutFormat.TXT
    @property
    def file_extension(self) -> str:
        return 'txt'

    @staticmethod
    def _extract_text(data):
        text = ""
        if isinstance(data, str):
            text = data
        elif isinstance(data, list):
            text = "".join(TxtProcessor._extract_text(item) for item in data)
        elif isinstance(data, dict):
            if "c" in data and data["c"] is not None:
                text = TxtProcessor._extract_text(data["c"])
        return text.replace("\u00ad", "")

    def process(self, source_dir: Path, book: TextBook) -> str:
        txt_files = sorted(
            f for f in source_dir.glob("*.txt")
        )
        results = []
        for file in txt_files:
            try:
                with file.open('r', encoding='utf-8', buffering=1024*1024) as infile:
                    raw = infile.read()
                    response_data = key_re.sub(r'\1"\2"\3', raw)
                    response_data = comma_re.sub(r'\1', response_data)
                    part_data = json.loads(response_data)
                    book_text_part = [
                        self._extract_text(text_block["c"])
                        for text_block in part_data if "c" in text_block
                    ]
                    results.append('\n'.join(book_text_part))
            except Exception as e:
                logger.error(f"Failed to parse part file {file}: {e}")
        return '\n'.join(results) 