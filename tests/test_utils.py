import pytest
from litres.utils import sanitize_filename, timing

@pytest.mark.parametrize("name,expected", [
    ("simple.txt", "simple.txt"),
    ("bad/file\\name.txt", "bad_file_name.txt"),
    ("with:colon|star?", "with_colon_star_"),
    ("trailing. ", "trailing."),  # updated expected value
])
def test_sanitize_filename(name, expected):
    assert sanitize_filename(name) == expected

def test_timing_decorator(mocker):
    mock_logger = mocker.patch("litres.utils.logger")
    @timing
    def foo(x):
        return x * 2
    result = foo(3)
    assert result == 6
    assert mock_logger.debug.call_count == 1
    assert "executed in" in mock_logger.debug.call_args[0][0] 