import requests

from ..config import logger
from ..constants import DOMAIN
from .browser_login import BrowserLogin
from .cookie_store import CookieStore

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def create_session() -> requests.Session:
    """Creates a new requests session with default headers."""
    session = requests.Session()
    session.headers.update(
        {"accept": "*/*", "user-agent": USER_AGENT, "referer": f"{DOMAIN}"}
    )
    return session


class AuthService:
    """Provides an authenticated LitRes session, using saved cookies or a login."""

    def __init__(
        self,
        cookie_store: CookieStore,
        browser_login: BrowserLogin,
        session: requests.Session | None = None,
    ):
        self._cookie_store = cookie_store
        self._browser_login = browser_login
        self._session = session or create_session()
        self.is_authenticated = False

    @property
    def session(self) -> requests.Session:
        """Provides access to the authenticated session."""
        if not self.is_authenticated:
            raise RuntimeError(
                "Session is not authenticated. Please call 'authenticate()' first."
            )
        return self._session

    def authenticate(self) -> bool:
        """Main authentication flow."""
        logger.debug("Starting authentication process")
        self._apply_cookies(self._cookie_store.load())

        if self._check_authentication():
            self.is_authenticated = True
            logger.info("Authentication successful with existing session.")
            return True

        logger.info(
            "Existing session is not valid. Starting manual login... (This may take several minutes)"
        )
        cookies = self._browser_login.run()
        if not cookies:
            logger.error("Manual login failed. Could not retrieve cookies.")
            self.is_authenticated = False
            return False

        self._cookie_store.save(cookies)
        self._apply_cookies(self._cookie_store.load())

        self.is_authenticated = self._check_authentication()
        if self.is_authenticated:
            logger.info("Manual login successful.")
        else:
            logger.error("Authentication failed after manual login.")

        return self.is_authenticated

    def _check_authentication(self) -> bool:
        """Checks if the current session is authenticated with LitRes."""
        try:
            sid = self._session.cookies.get("SID")
            if not sid:
                return False

            response = self._session.get(
                "https://api.litres.ru/foundation/api/users/me", timeout=10
            )

            if response.status_code == 200:
                return True

            logger.warning(f"Auth check failed with status {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"An error occurred during authentication check: {e}")
            return False

    def _apply_cookies(self, cookies: list[dict]) -> None:
        """Put cookies into the session and mirror SID into the API header."""
        for cookie in cookies:
            self._session.cookies.set(
                name=cookie["name"],
                value=cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

        sid_cookie = self._session.cookies.get("SID")
        if sid_cookie:
            self._session.headers.update({"session-id": sid_cookie})
        else:
            self._session.headers.pop("session-id", None)
