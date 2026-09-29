import os
from pathlib import Path


class BookPaths:
    def __init__(self, filename: str, source: Path, output: Path):
        self.filename = filename
        self.source = source
        self.output = output

    def makedirs(self):
        os.makedirs(self.source, exist_ok=True)
        os.makedirs(self.output, exist_ok=True)
