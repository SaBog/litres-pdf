import pytest

from litres.utils import sanitize_filename, timing


@pytest.mark.parametrize(
    "name,expected",
    [
        ("simple.txt", "simple.txt"),
        ("bad/file\\name.txt", "bad_file_name.txt"),
        ("with:colon|star?", "with_colon_star_"),
        ("trailing. ", "trailing."),  # updated expected value
    ],
)
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


def test_natural_sorted_orders_numeric_stems_by_value(tmp_path):
    from litres.utils import natural_sorted

    names = ["10.mp3", "2.mp3", "0.mp3", "1.mp3", "11.mp3", "cover.mp3"]
    result = [p.name for p in natural_sorted(tmp_path / n for n in names)]
    assert result == ["0.mp3", "1.mp3", "2.mp3", "10.mp3", "11.mp3", "cover.mp3"]


@pytest.mark.parametrize(
    "src,expected",
    [
        ('{a: 1, b: "x"}', {"a": 1, "b": "x"}),
        (r"{'a': 'it\'s'}", {"a": "it's"}),
        ('{"a": [1, 2,], }', {"a": [1, 2]}),
        ('{"t": "Война: и мир"}', {"t": "Война: и мир"}),
        ('{"t": "None of True or False"}', {"t": "None of True or False"}),
        ('{"t": "don\'t"}', {"t": "don't"}),
        ("{'t': 'say \"hi\"'}", {"t": 'say "hi"'}),
        ("{a: True, b: False, c: None}", {"a": True, "b": False, "c": None}),
    ],
)
def test_js_object_to_json(src, expected):
    import json

    from litres.utils import js_object_to_json

    assert json.loads(js_object_to_json(src)) == expected


def test_load_and_parse_content_keeps_part_order(tmp_path):
    import json

    from litres.utils import load_and_parse_content

    for i in (0, 1, 2, 10, 11):
        (tmp_path / f"{i}.txt").write_text(json.dumps([{"n": i}]), encoding="utf-8")
    assert [c["n"] for c in load_and_parse_content(tmp_path)] == [0, 1, 2, 10, 11]


def test_load_and_parse_content_does_not_corrupt_text(tmp_path):
    from litres.utils import load_and_parse_content

    (tmp_path / "0.txt").write_text(
        "[{'c': ['He said None', \"don't\"]}]", encoding="utf-8"
    )
    assert load_and_parse_content(tmp_path) == [{"c": ["He said None", "don't"]}]
