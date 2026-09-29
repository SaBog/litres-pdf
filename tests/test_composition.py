from unittest.mock import MagicMock

from litres.composition import build_book_processor
from litres.config.settings import AppSettings
from litres.engines.audio_merge import AudioMergeEngine
from litres.engines.o3.pdf_engine import IMG2PDFEngine
from litres.loaders.page_loader import PageImageLoader
from litres.models.book import BookFormat
from litres.models.out_format import OutFormat


def make_settings(**overrides) -> AppSettings:
    base = AppSettings(_env_file=None)
    values = {
        "quality": 42,
        "dpi": 111,
        "delay": 0.25,
        "max_workers": 7,
        "source_dir": "src",
        "books_dir": "out",
        "out_format_priority": [OutFormat.FB2],
    }
    return base.model_copy(update={**values, **overrides})


def test_build_registers_a_handler_for_every_book_format():
    bp = build_book_processor(MagicMock(), make_settings())
    assert set(bp.handlers) == set(BookFormat)


def test_build_passes_settings_to_engines_loaders_and_paths():
    bp = build_book_processor(MagicMock(), make_settings())
    o3 = bp.handlers[BookFormat.O3]
    audio = bp.handlers[BookFormat.AUDIOBOOK]

    engine = o3._engines[0]
    assert isinstance(engine, IMG2PDFEngine)
    assert (engine.quality, engine.dpi) == (42, 111)
    assert isinstance(audio._engines[0], AudioMergeEngine)

    loader = o3._loader
    assert isinstance(loader, PageImageLoader)
    assert (loader._delay, loader._max_workers) == (0.25, 7)
    assert str(o3._source_dir) == "src"
    assert str(o3._books_dir) == "out"
    assert bp._out_format_priority == [OutFormat.FB2]


def test_two_builds_do_not_share_engines():
    first = build_book_processor(MagicMock(), make_settings(quality=10))
    second = build_book_processor(MagicMock(), make_settings(quality=90))

    first_engine = first.handlers[BookFormat.O3]._engines[0]
    second_engine = second.handlers[BookFormat.O3]._engines[0]
    assert isinstance(first_engine, IMG2PDFEngine)
    assert isinstance(second_engine, IMG2PDFEngine)
    assert (first_engine.quality, second_engine.quality) == (10, 90)
