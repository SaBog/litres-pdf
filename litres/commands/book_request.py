
import requests

from litres.models.book import BookRequest
from litres.utils import extract_initial_state


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

    def __detect_book_format_and_file(self, art_files):
        """Detect book format (o3/o4) and select file_id based on file extensions."""
        o4_exts = {"txt", "txt.zip"}
        o3_exts = {"a4.pdf", "pdf", "a6.pdf"}
        file_id = None
        book_format = None
        # Сначала ищем по extension (старый способ)
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
        # Новый способ: если не нашли — ищем по filename и encoding_type
        if not file_id:
            for f in art_files or []:
                filename = f.get("filename", "")
                encoding_type = f.get("encoding_type", "")
                if filename.endswith(".pdf") and encoding_type == "pdf_book":
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
        state = extract_initial_state(resp.text)
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