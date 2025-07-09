import os
from pathlib import Path


class OutputPathHandler:
    def __init__(self, filename: str, source: Path, output: Path):
        self.filename = filename
        self.source = source
        self.output = output

        self.makedirs()

    def makedirs(self):
        os.makedirs(self.source, exist_ok=True)
        os.makedirs(self.output, exist_ok=True)

    def has_extension(self) -> bool:
        """Return True if the filename has an extension, False otherwise."""
        return Path(self.filename).suffix != ""