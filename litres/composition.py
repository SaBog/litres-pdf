"""Composition root: the one place that wires concrete classes together."""

from pathlib import Path

import requests

from litres.book_processor import BookProcessor
from litres.book_request import BookRequestResolver
from litres.config.settings import AppSettings
from litres.engines.audio_merge import AudioMergeEngine
from litres.engines.o3.pdf_engine import IMG2PDFEngine
from litres.engines.o4.fb2_engine import FB2Engine
from litres.engines.o4.pdf_engine import PDFEngine
from litres.engines.o4.txt_engine import TXTEngine
from litres.extractors.audiobook import AudiobookExtractor
from litres.extractors.o3 import O3Extractor
from litres.extractors.o4 import O4Extractor
from litres.extractors.reader_pdf import ReaderPdfExtractor
from litres.extractors.reader_text import ReaderTextExtractor
from litres.handlers.book_handler import BookHandler
from litres.loaders.audio_loader import AudioLoader
from litres.loaders.page_loader import PageImageLoader
from litres.loaders.reader_page_loader import ReaderPageLoader
from litres.loaders.reader_text_loader import ReaderTextLoader
from litres.loaders.text_loader import TextLoader
from litres.models.book import AudioBook, BookFormat, PdfBook, TextBook
from litres.services.auth_service import AuthService
from litres.services.browser_login import BrowserLogin
from litres.services.cookie_store import CookieStore
from litres.services.litres_api import LitresApi


def build_auth_service(settings: AppSettings) -> AuthService:
    return AuthService(CookieStore(settings.cookie_file), BrowserLogin())


def build_book_processor(
    session: requests.Session, settings: AppSettings
) -> BookProcessor:
    source_dir = Path(settings.source_dir)
    books_dir = Path(settings.books_dir)
    delay, max_workers = settings.delay, settings.max_workers
    api = LitresApi(session)

    handlers = {
        BookFormat.O3: BookHandler[PdfBook](
            O3Extractor(session),
            PageImageLoader(session, delay, max_workers),
            [IMG2PDFEngine(quality=settings.quality, dpi=settings.dpi)],
            source_dir,
            books_dir,
        ),
        BookFormat.PDF_READER: BookHandler[PdfBook](
            ReaderPdfExtractor(api),
            ReaderPageLoader(api, delay, max_workers),
            [IMG2PDFEngine(quality=settings.quality, dpi=settings.dpi)],
            source_dir,
            books_dir,
        ),
        BookFormat.TEXT_READER: BookHandler[TextBook](
            ReaderTextExtractor(api),
            ReaderTextLoader(api, delay, max_workers),
            [PDFEngine(), FB2Engine(), TXTEngine()],
            source_dir,
            books_dir,
        ),
        BookFormat.O4: BookHandler[TextBook](
            O4Extractor(session),
            TextLoader(session, delay, max_workers),
            [PDFEngine(), FB2Engine(), TXTEngine()],
            source_dir,
            books_dir,
        ),
        BookFormat.AUDIOBOOK: BookHandler[AudioBook](
            AudiobookExtractor(api),
            AudioLoader(session, delay, max_workers),
            [AudioMergeEngine()],
            source_dir,
            books_dir,
        ),
    }
    return BookProcessor(
        BookRequestResolver(session, api), handlers, settings.out_format_priority
    )
