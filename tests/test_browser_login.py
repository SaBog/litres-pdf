import subprocess
import sys
from unittest.mock import MagicMock, patch

from litres.services.browser_login import BrowserLogin


@patch("selenium.webdriver.support.ui.WebDriverWait")
@patch("selenium.webdriver.Chrome")
def test_run_opens_login_page_and_returns_cookies(mock_chrome, mock_wait):
    cookies = [{"name": "SID", "value": "123"}]
    driver = MagicMock()
    driver.get_cookies.return_value = cookies
    mock_chrome.return_value.__enter__.return_value = driver

    result = BrowserLogin(login_url="https://login/", timeout=5).run()

    assert result == cookies
    driver.get.assert_called_once_with("https://login/")
    assert mock_wait.call_args.args == (driver, 5)


@patch("selenium.webdriver.Chrome")
def test_run_returns_none_when_browser_fails(mock_chrome, mocker):
    mock_chrome.side_effect = Exception("Browser error")
    error = mocker.patch("litres.services.browser_login.logger.error")

    assert BrowserLogin().run() is None
    error.assert_called_once()


def test_importing_auth_modules_does_not_load_selenium():
    code = (
        "import sys, litres.services.auth_service, litres.services.browser_login;"
        "print('selenium' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"
