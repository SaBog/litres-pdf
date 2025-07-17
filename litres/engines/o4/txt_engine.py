from litres.config import logger
from litres.engines.base import Engine, OutFormat
from litres.models.output_path_handler import OutputPathHandler


class TXTEngine(Engine):
    SUPPORTED_OUT_FORMAT = OutFormat.TXT

    @staticmethod
    def _extract_text(data):
        text = ""
        if isinstance(data, str):
            text = data
        elif isinstance(data, list):
            text = "".join(TXTEngine._extract_text(item) for item in data)
        elif isinstance(data, dict):
            if "c" in data and data["c"] is not None:
                text = TXTEngine._extract_text(data["c"])
        return text.replace("\u00ad", "")

    def execute(self, book, path: OutputPathHandler):
        # book.parts is expected to be the structure for text extraction
        results = []
        for text_block in book.parts:
            if "c" in text_block:
                results.append(self._extract_text(text_block["c"]))
        result_text = '\n'.join(results)
        filename = path.output / (path.filename + '.txt')
        with open(filename, 'w', encoding='utf-8', buffering=1024*1024) as outfile:
            outfile.write(result_text)
        logger.info(f"Book text successfully saved to: {filename}") 
        