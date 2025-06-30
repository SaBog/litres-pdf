import pytest
from litres.utils import sanitize_filename, extract_file_id

def test_sanitize_filename():
    assert sanitize_filename('Test: Name/With\\Invalid*Chars?') == 'Test_ Name_With_Invalid_Chars_'
    assert sanitize_filename('A very long name that exceeds the maximum length of one hundred characters by a significant margin') == 'A very long name that exceeds the maximum length of one hundred characters by a significant margin'
    assert sanitize_filename('  Name with spaces  ') == 'Name with spaces'
    assert sanitize_filename('') == ''

@pytest.mark.parametrize("url, expected_id", [
    ("https://www.litres.ru/pages/get_pdf_js/?file=12345", "12345"),
    ("https://www.litres.ru/book/author/title-12345/", "12345"),
    ("https://www.litres.ru/static/or3/view/or.html?file=109410952&art=70974058", "109410952"),
    ("https://www.litres.ru/static/or/view/or.html?art=69399438&file=69399438", "69399438"),
    ("https://www.litres.ru/book/sergey-lukyanenko/gran-118966/", "118966"),
    ("https://litres.ru/12345/", "12345"),
    ("https://www.litres.ru/reader/or/69399438", "69399438"),
])
def test_extract_file_id(url, expected_id):
    assert extract_file_id(url) == expected_id 