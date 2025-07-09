
import json
import re

import requests

from litres.models.book import BookRequest


class BookRequestCommand():
    def __init__(self, session: requests.Session):
        self._session = session

    def __extract_user_id(self, state):
        """Extract user id from state structure."""
        user_queries = state.get("rtkqApi", {}).get("queries", {})
        for k, v in user_queries.items():
            if k.startswith("getUserDataForSSR") and "data" in v and "id" in v["data"]:
                return v["data"]["id"]
        return None
    
    def __extract_art_data_and_files(self, state):
        """Extract art_data and art_files from state structure."""
        user_queries = state.get("rtkqApi", {}).get("queries", {})
        art_data = None
        art_files = None
        for k, v in user_queries.items():
            if k.startswith('getArtData(') and 'data' in v:
                art_data = v['data']
                break
        for k, v in user_queries.items():
            if k.startswith('getArtFiles(') and 'data' in v:
                art_files = v['data']
                break
        return art_data, art_files
    
    def __extract_initial_state(self, html: str):
        """
        Extracts the 'initialState' JSON object from the given HTML string.
        """
        # Non-greedy match for the initialState value (handles escaped quotes and newlines)
        match = re.search(
            r'"initialState":"(.*?)"},"__N_SSP',
            html,
            re.DOTALL
        )
        if not match:
            raise ValueError("initialState not found in HTML")

        state_str_escaped = match.group(1)
        # Unescape unicode and escaped quotes
        try:
            state_str = bytes(state_str_escaped, "utf-8").decode("unicode_escape")
            state_json = json.loads(state_str)
        except Exception as e:
            raise ValueError(f"Failed to decode or parse initialState: {e}")

        return state_json

    def __detect_book_format_and_file(self, art_files):
        """Detect book format (o3/o4) and select file_id based on file extensions."""
        o4_exts = {"txt", "txt.zip"}
        o3_exts = {"a4.pdf", "pdf", "a6.pdf"}
        file_id = None
        book_format = None
        for f in art_files or []:
            ext = f.get("extension", "")
            if ext in o4_exts:
                file_id = f["id"]
                book_format = "o4"
                break
        if not file_id:
            for f in art_files or []:
                ext = f.get("extension", "")
                if ext in o3_exts:
                    file_id = f["id"]
                    book_format = "o3"
                    break
        return book_format, file_id
    
    def __generate_litres_url(self, book_format, art_type, art_id, file_id, user_id) -> str:
        """Generate the correct Litres viewer URL based on book format and parameters."""
        if not (book_format and art_id and file_id and user_id):
            return ''
        if book_format == 'o3':
            return f"https://www.litres.ru/static/or3/view/or.html?art_type={art_type}&file={file_id}&user={user_id}"
        elif book_format == 'o4':
            return f"https://www.litres.ru/static/or4/view/or.html?baseurl=/download_book_subscr/{art_id}/{file_id}/&art={art_id}&user={user_id}"
        return ''

    def create(self, url: str):
        resp = self._session.get(url)
        resp.raise_for_status()
        state = self.__extract_initial_state(resp.text)
        user_id = self.__extract_user_id(state)

        art_data, art_files = self.__extract_art_data_and_files(state)
        art_type = art_data.get('art_type') if art_data else None
        book_format, file_id = self.__detect_book_format_and_file(art_files)
        art_id = art_data.get('id') if art_data else None
        base_url = f"/download_book_subscr/{art_id}/{file_id}/" if (art_id and file_id) else None

        url = self.__generate_litres_url(book_format, art_type, art_id, file_id, user_id)

        return BookRequest(
            url=url,
            file_id=file_id,
            art_id=art_id,
            base_url=base_url
        )