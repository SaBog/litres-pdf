import threading

import requests

from litres.config import logger
from litres.constants import DOMAIN
from litres.exceptions import BookProcessingError

from .auth_service import create_session

API_BASE = "https://api.litres.ru/foundation/api"
APP_ID = "115"
CLIENT_HOST = "www.litres.ru"
REQUEST_TIMEOUT = 30


class LitresApi:
    """Talks to the LitRes foundation API the way the web reader does.

    Files (page images, book config) are never served by the API itself: it hands
    out short-lived signed links, which are then fetched anonymously.
    """

    def __init__(
        self, session: requests.Session, content_session: requests.Session | None = None
    ):
        self.session = session
        # Signed links are self-contained; don't send our cookies/session headers
        self._content_session = content_session or create_session()
        self._drm_lock = threading.Lock()
        self._drm: dict[str, dict[str, str]] = {}

    def _headers(self) -> dict[str, str]:
        headers = {
            "App-Id": APP_ID,
            "Client-host": CLIENT_HOST,
            "Ui-Language-Code": "ru",
            "ui-currency": "RUB",
        }
        if sid := self.session.cookies.get("SID"):
            headers["Session-Id"] = sid
        if supersid := self.session.cookies.get("supersid"):
            headers["supersid"] = supersid
        return headers

    def drm_params(self, art_id: str | None) -> dict[str, str]:
        """Signature query params (timestamp, md5) for file links; {} if none."""
        if not art_id:
            return {}
        with self._drm_lock:
            if art_id not in self._drm:
                self._drm[art_id] = self._fetch_drm(art_id)
            return self._drm[art_id]

    def reset_drm(self) -> None:
        """Forget cached signatures so the next call asks for fresh ones."""
        with self._drm_lock:
            self._drm.clear()

    def _fetch_drm(self, art_id: str) -> dict[str, str]:
        try:
            response = self.session.get(
                f"{API_BASE}/arts/{art_id}",
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Could not fetch DRM signature for art {art_id}: {e!s}")
            return {}

        timestamp, _, md5 = response.headers.get("Drm3-Key", "").partition(":")
        if timestamp.isdigit() and int(timestamp) and md5:
            return {"timestamp": timestamp, "md5": md5}
        return {}

    def file_link(self, file_id: str, **query: str | int) -> str:
        """Signed download link for a file (config with index=1, or a page)."""
        response = self.session.get(
            f"{API_BASE}/arts/files/{file_id}/link",
            params=query,
            headers=self._headers(),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        data = (body.get("payload") or {}).get("data") or {}
        link = data.get("link")
        if body.get("status") != 200 or not link:
            raise BookProcessingError(
                f"Unexpected link response for file {file_id}: {str(body)[:200]}"
            )
        return link

    def resource_link(
        self, file_id: str, resource: str, art_id: str | None = None
    ) -> str:
        """Signed link for a named file resource (toc.js, a text part, an image).

        Like the text reader: ask without a DRM signature first and only fetch one
        if the server answers 422.
        """
        query = {"resource": resource.lower(), "is_trial": "false"}
        try:
            return self.file_link(file_id, **query)
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 422 or not art_id:
                raise
            drm = self.drm_params(art_id)
            if not drm:
                raise
            return self.file_link(file_id, **query, **drm)

    def art(self, art_id: str) -> dict:
        """Public information about an art (title, type, ...)."""
        response = self.session.get(
            f"{API_BASE}/arts/{art_id}",
            headers=self._headers(),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = (response.json().get("payload") or {}).get("data")
        if not isinstance(data, dict):
            raise BookProcessingError(f"Unexpected art response for art {art_id}")
        return data

    def art_files(self, art_id: str) -> list[dict]:
        """Every file listed for an art (public); the current one has extensions set."""
        response = self.session.get(
            f"{API_BASE}/arts/{art_id}/files",
            headers=self._headers(),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        files = ((response.json().get("payload") or {}).get("data")) or []
        if not isinstance(files, list):
            raise BookProcessingError(f"Unexpected files response for art {art_id}")
        return files

    def legacy_asset(self, art_id: str, file_id: str, name: str) -> requests.Response:
        """A file from the pre-API download path, authenticated by our session."""
        response = self.session.get(
            f"{DOMAIN}download_book_subscr/{art_id}/{file_id}/json/{name}",
            stream=True,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response

    def download(self, url: str) -> requests.Response:
        """Fetch a signed content link anonymously (streamed)."""
        response = self._content_session.get(url, stream=True, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response
