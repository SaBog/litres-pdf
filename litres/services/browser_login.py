from ..config import logger

LOGIN_URL = "https://www.litres.ru/pages/login/"
LOGIN_TIMEOUT_SECONDS = 300


class BrowserLogin:
    """Opens a browser for the user to log in manually and returns its cookies."""

    def __init__(
        self, login_url: str = LOGIN_URL, timeout: int = LOGIN_TIMEOUT_SECONDS
    ):
        self._login_url = login_url
        self._timeout = timeout

    def run(self) -> list[dict] | None:
        # Imported here so a valid saved session never pays for loading Selenium
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait

        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")

        try:
            with webdriver.Chrome(options=chrome_options) as driver:
                driver.get(self._login_url)
                WebDriverWait(driver, self._timeout).until(
                    lambda d: "login" not in d.current_url.lower()
                )
                return driver.get_cookies()
        except Exception as e:
            logger.error(f"An error occurred during manual login: {e}", exc_info=True)
            return None
