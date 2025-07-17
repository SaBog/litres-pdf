import json
from pathlib import Path
from typing import Dict, List, Optional

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from ..config import app_settings, logger
from ..constants import DOMAIN


class AuthService:
    """Handles authentication, session, and browser management."""

    def __init__(self):
        self._session: requests.Session = self._create_session()
        self.is_authenticated = False

    def _create_session(self) -> requests.Session:
        """Creates a new requests session with default headers."""
        session = requests.Session()
        session.headers.update({
            "accept": "*/*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "referer": f"{DOMAIN}",
        })
        return session

    @property
    def session(self) -> requests.Session:
        """Provides access to the authenticated session."""
        if not self.is_authenticated:
            raise RuntimeError("Session is not authenticated. Please call 'authenticate()' first.")
        return self._session

    def authenticate(self) -> bool:
        """Main authentication flow."""
        logger.debug("Starting authentication process")
        self._load_cookies(app_settings.cookie_file)

        if self._check_authentication():
            self.is_authenticated = True
            logger.info("Authentication successful with existing session.")
            return True
        
        logger.info("Existing session is not valid. Starting manual login...")
        cookies = self._manual_login()
        if not cookies:
            logger.error("Manual login failed. Could not retrieve cookies.")
            self.is_authenticated = False
            return False

        self._save_cookies(app_settings.cookie_file, cookies)
        self._load_cookies(app_settings.cookie_file)

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
                "https://api.litres.ru/foundation/api/users/me",
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            
            logger.warning(f"Auth check failed with status {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"An error occurred during authentication check: {e}")
            return False

    def _load_cookies(self, cookie_path: Path) -> None:
        """Load cookies from a JSON file into the session."""
        if not cookie_path.exists():
            logger.warning(f"Cookie file not found: {cookie_path}")
            return

        try:
            with cookie_path.open('r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            for cookie in cookies:
                self._session.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie.get('domain'),
                    path=cookie.get('path', '/')
                )
            
            # Sync the SID cookie to the session headers for API calls
            sid_cookie = self._session.cookies.get("SID")
            if sid_cookie:
                self._session.headers.update({"session-id": sid_cookie})
            else:
                self._session.headers.pop("session-id", None)
                
            logger.info(f"Loaded {len(cookies)} cookies from {cookie_path}")
        except Exception as e:
            logger.error(f"Failed to load cookies from {cookie_path}: {e}")

    def _save_cookies(self, cookie_path: Path, cookies: List[Dict]) -> None:
        """Saves the essential SID cookie to a JSON file."""
        sid_cookie = next((c for c in cookies if c.get('name') == 'SID'), None)

        if not sid_cookie:
            logger.warning("No SID cookie found to save.")
            return

        try:
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            with cookie_path.open('w', encoding='utf-8') as f:
                json.dump([sid_cookie], f, indent=2)
            logger.info(f"SID cookie saved to {cookie_path}")
        except Exception as e:
            logger.error(f"Failed to save cookie file {cookie_path}: {e}")
            
    def _manual_login(self) -> Optional[List[Dict]]:
        """Opens a browser for the user to log in manually."""
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")

        try:
            with webdriver.Chrome(options=chrome_options) as driver:
                driver.get("https://www.litres.ru/pages/login/")
                WebDriverWait(driver, 300).until(
                    lambda d: "login" not in d.current_url.lower()
                )
                return driver.get_cookies()
        except Exception as e:
            logger.error(f"An error occurred during manual login: {e}", exc_info=True)
            return None 