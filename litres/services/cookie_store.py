import json
from pathlib import Path

from ..config import logger

SESSION_COOKIES = ("SID", "supersid")


class CookieStore:
    """Persists the session cookie (SID) in a JSON file."""

    def __init__(self, path: Path):
        self._path = path

    def load(self) -> list[dict]:
        """Return the stored cookies, or an empty list if there are none."""
        if not self._path.exists():
            logger.warning(f"Cookie file not found: {self._path}")
            return []

        try:
            with self._path.open("r", encoding="utf-8") as f:
                cookies = json.load(f)
            logger.info(f"Loaded {len(cookies)} cookies from {self._path}")
            return cookies
        except Exception as e:
            logger.error(f"Failed to load cookies from {self._path}: {e}")
            return []

    def save(self, cookies: list[dict]) -> bool:
        """Store the session cookies (SID, supersid). Returns whether it was saved."""
        kept = [c for c in cookies if c.get("name") in SESSION_COOKIES]

        if not any(c.get("name") == "SID" for c in kept):
            logger.warning("No SID cookie found to save.")
            return False

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(kept, f, indent=2)
            logger.info(f"Session cookies saved to {self._path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save cookie file {self._path}: {e}")
            return False
