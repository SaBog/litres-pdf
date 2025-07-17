from unittest.mock import MagicMock

import pytest

from litres.commands.book_request import BookRequestCommand


# __extract_user_id
@pytest.mark.parametrize("state,expected", [
    ({"rtkqApi": {"queries": {"getUserDataForSSR": {"data": {"id": 123}}}}}, 123),
    ({"rtkqApi": {"queries": {}}}, None),
    ({}, None),
])
def test_extract_user_id(state, expected):
    cmd = BookRequestCommand(MagicMock())
    method = getattr(cmd, '_BookRequestCommand__extract_user_id')
    assert method(state) == expected

# __extract_art_data_and_files
@pytest.mark.parametrize("state,expected_art,expected_files", [
    ({"rtkqApi": {"queries": {"getArtData(1)": {"data": {"id": 1, "art_type": "book"}}, "getArtFiles(1)": {"data": [{"id": "f1", "extension": "pdf"}]}}}}, {"id": 1, "art_type": "book"}, [{"id": "f1", "extension": "pdf"}]),
    ({"rtkqApi": {"queries": {}}}, None, None),
])
def test_extract_art_data_and_files(state, expected_art, expected_files):
    cmd = BookRequestCommand(MagicMock())
    method = getattr(cmd, '_BookRequestCommand__extract_art_data_and_files')
    art, files = method(state)
    assert art == expected_art
    assert files == expected_files


# __detect_book_format_and_file
@pytest.mark.parametrize("art_files,expected_format,expected_file_id", [
    ([{"id": "f1", "extension": "txt"}], "o4", "f1"),
    ([{"id": "f2", "extension": "pdf"}], "o3", "f2"),
    ([{"id": "f3", "extension": "unknown"}], None, None),
    ([], None, None),
    (None, None, None),
])
def test_detect_book_format_and_file(art_files, expected_format, expected_file_id):
    cmd = BookRequestCommand(MagicMock())
    method = getattr(cmd, '_BookRequestCommand__detect_book_format_and_file')
    fmt, file_id = method(art_files)
    assert fmt == expected_format
    assert file_id == expected_file_id

# __generate_litres_url
@pytest.mark.parametrize("book_format,art_type,art_id,file_id,user_id,expected", [
    ("o3", "book", "aid", "fid", "uid", "https://www.litres.ru/static/or3/view/or.html?art_type=book&file=fid&user=uid"),
    ("o4", "book", "aid", "fid", "uid", "https://www.litres.ru/static/or4/view/or.html?baseurl=/download_book_subscr/aid/fid/&art=aid&user=uid"),
    (None, "book", "aid", "fid", "uid", ""),
    ("o3", None, None, None, None, ""),
])
def test_generate_litres_url(book_format, art_type, art_id, file_id, user_id, expected):
    cmd = BookRequestCommand(MagicMock())
    method = getattr(cmd, '_BookRequestCommand__generate_litres_url')
    url = method(book_format, art_type, art_id, file_id, user_id)
    assert url == expected


def test_create_initial_state_error(monkeypatch):
    session = MagicMock()
    session.get.return_value.text = "no initialState here"
    session.get.return_value.raise_for_status = lambda: None
    cmd = BookRequestCommand(session)
    with pytest.raises(ValueError):
        cmd.create("http://test") 