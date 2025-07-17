from litres.commands.extract_audiobook import ExtractAudiobookCommand
from litres.config import logger
from litres.engines.audio_merge import AudioMergeEngine
from litres.handlers.base import BaseUrlHandler
from litres.loaders.audio_loader import AudioLoaderCommand
from litres.models.book import BookRequest


class HandlerUrlAudiobook(BaseUrlHandler):
    engines = [AudioMergeEngine()]

    def supports(self, bq: BookRequest) -> bool:
        return '/audiobook/' in bq.url

    def load(self, bq: BookRequest):
        self.book = ExtractAudiobookCommand(self._session).get(bq.url)
        logger.info(f"Fetched audiobook meta. Title: {self.book.meta.title}")
        AudioLoaderCommand(self._session).download_parts(self.book, self.path_handler) 