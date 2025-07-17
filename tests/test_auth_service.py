import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from litres.config import logger
from litres.constants import DOMAIN
from litres.services.auth_service import AuthService


class TestAuthService:
    """Test suite for AuthService class."""

    @patch("requests.Session")
    def test_create_session(self, mock_session):
        """Test session creation with proper headers."""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        
        auth = AuthService()
        
        mock_session.assert_called_once()
        mock_session_instance.headers.update.assert_called_once_with({
            "accept": "*/*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "referer": f"{DOMAIN}",
        })

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_load_cookies(self, mock_file, mock_exists):
        """Test loading cookies from file."""
        mock_exists.return_value = True
        test_cookies = [{"name": "SID", "value": "123", "domain": "example.com"}]
        mock_file.return_value.read.return_value = json.dumps(test_cookies)
        
        auth = AuthService()
        auth._session = MagicMock()
        auth._session.cookies = MagicMock()
        # Mock the specific cookie getter behavior
        auth._session.cookies.get.return_value = "123"
        
        auth._load_cookies(Path("test.json"))
        
        mock_exists.assert_called_once()
        mock_file.assert_called_once_with('r', encoding='utf-8')
        auth._session.cookies.set.assert_called_once_with(
            name="SID", value="123", domain="example.com", path="/"
        )
        auth._session.headers.update.assert_called_once_with({"session-id": "123"})

    @patch("pathlib.Path.exists")
    def test_load_cookies_file_not_found(self, mock_exists):
        """Test handling of missing cookie file."""
        mock_exists.return_value = False
        
        auth = AuthService()
        auth._load_cookies(Path("missing.json"))
        
        mock_exists.assert_called_once()

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_save_cookies(self, mock_file_open, mock_mkdir):
        """Test saving cookies to file."""
        test_cookies = [
            {"name": "OTHER", "value": "456"},
            {"name": "SID", "value": "123"}
        ]

        auth = AuthService()
        auth._save_cookies(Path("test.json"), test_cookies)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file_open.assert_called_once_with('w', encoding='utf-8')

        # Access the actual file handle mock
        file_handle = mock_file_open()

        # Ensure write() was called at least once
        assert file_handle.write.called, "No content was written to the file."

        # Get the content written to the file (json.dump writes all at once)
        written_str = ''.join(call.args[0] for call in file_handle.write.call_args_list)

        # Parse it
        saved_data = json.loads(written_str)

        # Assertions
        assert isinstance(saved_data, list)
        assert len(saved_data) == 1
        assert saved_data[0]["name"] == "SID"
        assert saved_data[0]["value"] == "123"

    def test_save_cookies_no_sid(self):
        """Test handling of missing SID cookie."""
        test_cookies = [{"name": "OTHER", "value": "456"}]
        
        auth = AuthService()
        auth._save_cookies(Path("test.json"), test_cookies)

    @patch("requests.Session.get")
    def test_check_authentication_success(self, mock_get):
        """Test successful authentication check."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Create auth service with proper session mock
        auth = AuthService()
        auth._session = MagicMock()
        # Ensure cookies.get returns a non-empty string
        auth._session.cookies.get.return_value = "valid_sid"
        auth._session.get = mock_get
        
        result = auth._check_authentication()
        
        assert result is True
        mock_get.assert_called_once_with(
            "https://api.litres.ru/foundation/api/users/me",
            timeout=10
        )

    @patch("requests.Session.get")
    def test_check_authentication_failure(self, mock_get):
        """Test failed authentication check."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        auth = AuthService()
        auth._session = MagicMock()
        auth._session.cookies.get.return_value = "invalid_sid"
        
        result = auth._check_authentication()
        
        assert result is False

    @patch("selenium.webdriver.Chrome")
    def test_manual_login_success(self, mock_chrome):
        """Test successful manual login."""
        # Create a real list of cookies, not a MagicMock
        test_cookies = [{"name": "SID", "value": "123", "domain": "example.com"}]
        
        mock_driver = MagicMock()
        # Use side_effect or return_value properly
        mock_driver.get_cookies.return_value = test_cookies
        # Properly mock context manager
        mock_chrome.return_value.__enter__.return_value = mock_driver
        mock_chrome.return_value.__exit__.return_value = None
        
        auth = AuthService()
        result = auth._manual_login()
        
        # Compare the actual returned cookies
        assert isinstance(result, list)
        assert result == test_cookies
        mock_driver.get.assert_called_once_with("https://www.litres.ru/pages/login/")

    @patch("selenium.webdriver.Chrome")
    def test_manual_login_failure(self, mock_chrome):
        """Test failed manual login."""
        mock_chrome.side_effect = Exception("Browser error")
        
        auth = AuthService()
        result = auth._manual_login()
        
        assert result is None

    @patch.object(AuthService, "_check_authentication")
    @patch.object(AuthService, "_load_cookies")
    def test_authenticate_with_valid_cookies(self, mock_load, mock_check):
        """Test authentication with valid existing cookies."""
        mock_check.return_value = True
        
        auth = AuthService()
        result = auth.authenticate()
        
        assert result is True
        assert auth.is_authenticated is True
        mock_load.assert_called_once()
        mock_check.assert_called_once()

    @patch.object(AuthService, "_check_authentication")
    @patch.object(AuthService, "_load_cookies")
    @patch.object(AuthService, "_manual_login")
    @patch.object(AuthService, "_save_cookies")
    def test_authenticate_with_manual_login(self, mock_save, mock_manual, mock_load, mock_check):
        """Test authentication requiring manual login."""
        mock_check.side_effect = [False, True]
        mock_manual.return_value = [{"name": "SID", "value": "123"}]
        
        auth = AuthService()
        result = auth.authenticate()
        
        assert result is True
        assert auth.is_authenticated is True
        assert mock_load.call_count == 2
        mock_manual.assert_called_once()
        mock_save.assert_called_once()
        assert mock_check.call_count == 2

    def test_session_property_unauthenticated(self):
        """Test session property raises when not authenticated."""
        auth = AuthService()
        auth.is_authenticated = False
        
        with pytest.raises(RuntimeError, match="Session is not authenticated"):
            _ = auth.session

    @patch("requests.Session.get")
    def test_check_authentication_exception(self, mock_get):
        """Test _check_authentication handles exceptions and logs error."""
        mock_get.side_effect = Exception("Network error")
        auth = AuthService()
        auth._session = MagicMock()
        auth._session.cookies.get.return_value = "valid_sid"
        auth._session.get = mock_get
        with patch.object(logger, "error") as mock_log_error:
            result = auth._check_authentication()
            assert result is False
            mock_log_error.assert_called()

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_load_cookies_json_error(self, mock_file_open, mock_exists):
        """Test _load_cookies handles JSON decode error and logs error."""
        mock_exists.return_value = True
        mock_file_open.return_value.read.side_effect = ValueError("bad json")
        auth = AuthService()
        auth._session = MagicMock()
        with patch.object(logger, "error") as mock_log_error:
            auth._load_cookies(Path("test.json"))
            mock_log_error.assert_called()

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_save_cookies_write_error(self, mock_file_open, mock_mkdir):
        """Test _save_cookies handles file write error and logs error."""
        test_cookies = [{"name": "SID", "value": "123"}]
        mock_file_open.side_effect = Exception("write error")
        auth = AuthService()
        with patch.object(logger, "error") as mock_log_error:
            auth._save_cookies(Path("test.json"), test_cookies)
            mock_log_error.assert_called()

    @patch("pathlib.Path.exists")
    def test_load_cookies_file_not_found_logs_warning(self, mock_exists):
        """Test _load_cookies logs warning if file not found."""
        mock_exists.return_value = False
        auth = AuthService()
        with patch.object(logger, "warning") as mock_log_warning:
            auth._load_cookies(Path("missing.json"))
            mock_log_warning.assert_called()

    def test_save_cookies_no_sid_logs_warning(self):
        """Test _save_cookies logs warning if SID is missing."""
        test_cookies = [{"name": "OTHER", "value": "456"}]
        auth = AuthService()
        with patch.object(logger, "warning") as mock_log_warning:
            auth._save_cookies(Path("test.json"), test_cookies)
            mock_log_warning.assert_called()

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_load_cookies_missing_optional_fields(self, mock_file_open, mock_exists):
        """Test _load_cookies with cookies missing domain/path fields."""
        mock_exists.return_value = True
        test_cookies = [{"name": "SID", "value": "123"}]  # No domain/path
        mock_file_open.return_value.read.return_value = json.dumps(test_cookies)
        auth = AuthService()
        auth._session = MagicMock()
        auth._session.cookies = MagicMock()
        auth._session.cookies.get.return_value = "123"
        auth._session.headers.update = MagicMock()
        auth._load_cookies(Path("test.json"))
        auth._session.cookies.set.assert_called_once_with(
            name="SID", value="123", domain=None, path="/"
        )
        auth._session.headers.update.assert_called_once_with({"session-id": "123"})