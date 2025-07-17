from litres.config import logger
from litres.engines.base import Engine, OutFormat
from litres.models.output_path_handler import OutputPathHandler


class AudioMergeEngine(Engine):
    SUPPORTED_OUT_FORMAT = OutFormat.MP3

    # TODO: Use ffmpeg to concatenate
    def execute(self, book, path: OutputPathHandler):
        mp3_files = sorted(path.source.glob('*.mp3'))
        if not mp3_files:
            logger.error('No mp3 files found to merge!')
            return
        
        output_file = path.output / (path.filename + '.mp3')

        with output_file.open('wb') as outfile:
            for f in mp3_files:
                with f.open('rb') as infile:
                    outfile.write(infile.read())

        logger.info(f'Merged {len(mp3_files)} mp3 files into {output_file}') 