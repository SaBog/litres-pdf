import json
from litres.config import logger
from litres.engines.base import Engine, OutFormat
from litres.models.output_path_handler import OutputPathHandler
from litres.utils import key_re, comma_re

class O4ToTXTEngine(Engine):
    SUPPORTED_OUT_FORMAT = OutFormat.TXT

    @staticmethod
    def _extract_text(data):
        text = ""
        if isinstance(data, str):
            text = data
        elif isinstance(data, list):
            text = "".join(O4ToTXTEngine._extract_text(item) for item in data)
        elif isinstance(data, dict):
            if "c" in data and data["c"] is not None:
                text = O4ToTXTEngine._extract_text(data["c"])
        return text.replace("\u00ad", "")

    def execute(self, path: OutputPathHandler):
        txt_files = sorted(
            f for f in path.source.glob("*.txt")
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
        
        result_text = '\n'.join(results) 
        filename = path.output / (path.filename + '.txt')

        with open(filename, 'w', encoding='utf-8', buffering=1024*1024) as outfile:
            outfile.write(result_text)

        logger.info(f"Book text successfully saved to: {filename}") 
        