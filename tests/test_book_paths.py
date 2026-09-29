import tempfile
from pathlib import Path

from litres.models.book_paths import BookPaths


def test_book_paths_constructor_has_no_side_effects():
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source"
        output = Path(tmpdir) / "output"
        BookPaths("file.txt", source, output)
        assert not source.exists()
        assert not output.exists()


def test_book_paths_makedirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source"
        output = Path(tmpdir) / "output"
        handler = BookPaths("file.txt", source, output)
        handler.makedirs()
        handler.makedirs()  # idempotent
        assert source.is_dir()
        assert output.is_dir()
