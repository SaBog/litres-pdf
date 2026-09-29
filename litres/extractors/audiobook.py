import re

import requests

from litres.models.book import AudioBook, AudioPart, Author, BookMeta, BookRequest
from litres.parsing import find_query
from litres.utils import extract_initial_state


class AudiobookExtractor:
    def __init__(self, session: requests.Session):
        self._session = session

    def get(self, bq: BookRequest) -> AudioBook:
        resp = self._session.get(bq.url)
        resp.raise_for_status()
        state = extract_initial_state(resp.text)
        meta = self._extract_meta(state)
        art_id, parts = self._extract_mp3_parts(state)
        return AudioBook(meta=meta, art_id=art_id, parts=parts)

    def _extract_meta(self, state):
        title = "Аудиокнига"
        art_data_query = find_query(state, "getArtData({")
        if art_data_query:
            book_title = art_data_query[1].get("data", {}).get("title")
            if book_title:
                title += " " + book_title
        authors = [Author(first="Litres")]  # TODO: можно доработать авторов
        return BookMeta(authors=authors, title=title, version=1.0, uuid="audiobook")

    def _extract_mp3_parts(self, state) -> tuple[str, list[AudioPart]]:
        art_files_query = find_query(state, "getArtFiles({")
        if not art_files_query:
            raise ValueError("Не найден ключ getArtFiles в initialState")
        art_files_key, art_files_value = art_files_query
        m = re.search(r'"artId":(\d+)', art_files_key)
        if not m:
            raise ValueError("Не удалось извлечь artId из ключа getArtFiles")
        art_id = m.group(1)
        files = art_files_value.get("data", [])
        mp3_files = [
            f
            for f in files
            if f.get("filename", "").endswith(".mp3")
            and f.get("encoding_type") == "standard_quality_mp3"
        ]
        parts: list[AudioPart] = []
        for f in mp3_files:
            file_id = f["id"]
            filename = f["filename"]
            url = f"https://www.litres.ru/download_book_subscr/{art_id}/{file_id}/{filename}"
            parts.append({"filename": filename, "file_id": file_id, "url": url})
        return art_id, parts
