import shutil

from litres.config import logger
from litres.engines.base import Engine
from litres.exceptions import BookProcessingError
from litres.models.book import AudioBook
from litres.models.book_paths import BookPaths
from litres.models.out_format import OutFormat
from litres.utils import natural_sorted


class AudioMergeEngine(Engine[AudioBook]):
    SUPPORTED_OUT_FORMAT = OutFormat.MP3

    # TODO: Use ffmpeg to concatenate
    def execute(self, book: AudioBook, path: BookPaths) -> None:
        mp3_files = natural_sorted(path.source.glob("*.mp3"))
        if not mp3_files:
            raise BookProcessingError("No mp3 files found to merge")

        output_file = path.output / (path.filename + ".mp3")

        with output_file.open("wb") as outfile:
            for f in mp3_files:
                with f.open("rb") as infile:
                    shutil.copyfileobj(infile, outfile)

        logger.info(f"Merged {len(mp3_files)} mp3 files into {output_file}")
