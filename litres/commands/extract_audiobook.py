import re

import requests

from litres.models.book import AudioBook, Author, BookMeta
from litres.utils import extract_initial_state


class ExtractAudiobookCommand:
    def __init__(self, session: requests.Session):
        self._session = session

    def get(self, url: str) -> AudioBook:
        resp = self._session.get(url)
        resp.raise_for_status()
        state = extract_initial_state(resp.text)
        meta = self._extract_meta(state)
        art_id, parts = self._extract_mp3_parts(state)
        return AudioBook(meta=meta, art_id=art_id, parts=parts)

    def _extract_meta(self, state):
        queries = state.get("rtkqApi", {}).get("queries", {})
        # Найти ключ getArtData
        art_data_key = next((k for k in queries if k.startswith("getArtData({")), None)
        title = "Аудиокнига"
        if art_data_key:
            art_data = queries[art_data_key].get("data", {})
            title += ' ' + art_data.get("title", title)
        authors = [Author(first="Litres")]  # TODO: можно доработать авторов
        return BookMeta(authors=authors, title=title, version=1.0, uuid="audiobook")

    def _extract_mp3_parts(self, state):
        queries = state.get("rtkqApi", {}).get("queries", {})
        art_files_key = next((k for k in queries if k.startswith("getArtFiles({")), None)
        if not art_files_key:
            raise ValueError("Не найден ключ getArtFiles в initialState")
        m = re.search(r'"artId":(\d+)', art_files_key)
        if not m:
            raise ValueError("Не удалось извлечь artId из ключа getArtFiles")
        art_id = m.group(1)
        files = queries[art_files_key].get("data", [])
        mp3_files = [f for f in files if f.get("filename", "").endswith(".mp3") and f.get("encoding_type") == "standard_quality_mp3"]
        parts = []
        for f in mp3_files:
            file_id = f["id"]
            filename = f["filename"]
            url = f"https://www.litres.ru/download_book_subscr/{art_id}/{file_id}/{filename}"
            parts.append({"filename": filename, "file_id": file_id, "url": url})
        return art_id, parts 