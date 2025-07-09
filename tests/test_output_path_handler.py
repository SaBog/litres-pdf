import tempfile
from pathlib import Path
from litres.models.output_path_handler import OutputPathHandler

def test_output_path_handler_makedirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source"
        output = Path(tmpdir) / "output"
        # call make dirs under hood
        OutputPathHandler("file.txt", source, output)
        assert source.exists()
        assert output.exists()

def test_output_path_handler_has_extension():
    in_path = Path("/tmp/source")
    out_path = Path("/tmp/source")
    
    handler = OutputPathHandler("file.txt", in_path, out_path)
    assert handler.has_extension() is True
    handler = OutputPathHandler("file", in_path, out_path)
    assert handler.has_extension() is False 