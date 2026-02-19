"""Session management and browser cookie extraction for IMHentai."""

import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from urllib.parse import urlparse


class SessionManager:
    """Manages HTTP sessions with browser cookies."""

    IMHENTAI_DOMAIN = "imhentai.xxx"


    SUPPORTED_BROWSERS = ["firefox", "chrome", "brave", "edge", "opera", "safari"]

    def __init__(self, browser: str = "firefox"):
        """Initialize session manager.
        
        Args:
            browser: Browser to extract cookies from ('firefox', 'chrome', 'brave', 'edge', 'opera', 'safari').
        """
        self.browser = browser.lower()
        if self.browser not in self.SUPPORTED_BROWSERS:
            raise ValueError(f"Unsupported browser: {self.browser}. Supported: {', '.join(self.SUPPORTED_BROWSERS)}")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self._load_cookies()

    def _load_cookies(self) -> None:
        """Load cookies from browser."""
        if self.browser == "firefox":
            self._load_firefox_cookies()
        elif self.browser == "chrome":
            self._load_chrome_cookies()
        elif self.browser == "brave":
            self._load_brave_cookies()
        elif self.browser == "edge":
            self._load_edge_cookies()
        elif self.browser == "opera":
            self._load_opera_cookies()
        elif self.browser == "safari":
            self._load_safari_cookies()
        else:
            raise ValueError(f"Unsupported browser: {self.browser}")
    def _load_brave_cookies(self) -> None:
        """Load cookies from Brave profile (Chromium-based)."""
        brave_cookies_path = Path.home() / "AppData" / "Local" / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cookies"
        if not brave_cookies_path.exists():
            return
        try:
            conn = sqlite3.connect(brave_cookies_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, value, host_key FROM cookies WHERE host_key LIKE ?",
                (f"%{self.IMHENTAI_DOMAIN}%",)
            )
            for name, value, domain in cursor.fetchall():
                self.session.cookies.set(name, value, domain=domain)
            conn.close()
        except Exception as e:
            print(f"Warning: Could not load Brave cookies: {e}")

    def _load_edge_cookies(self) -> None:
        """Load cookies from Edge profile (Chromium-based)."""
        edge_cookies_path = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data" / "Default" / "Cookies"
        if not edge_cookies_path.exists():
            return
        try:
            conn = sqlite3.connect(edge_cookies_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, value, host_key FROM cookies WHERE host_key LIKE ?",
                (f"%{self.IMHENTAI_DOMAIN}%",)
            )
            for name, value, domain in cursor.fetchall():
                self.session.cookies.set(name, value, domain=domain)
            conn.close()
        except Exception as e:
            print(f"Warning: Could not load Edge cookies: {e}")

    def _load_opera_cookies(self) -> None:
        """Load cookies from Opera profile (Chromium-based)."""
        opera_cookies_path = Path.home() / "AppData" / "Roaming" / "Opera Software" / "Opera Stable" / "Cookies"
        if not opera_cookies_path.exists():
            return
        try:
            conn = sqlite3.connect(opera_cookies_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, value, host_key FROM cookies WHERE host_key LIKE ?",
                (f"%{self.IMHENTAI_DOMAIN}%",)
            )
            for name, value, domain in cursor.fetchall():
                self.session.cookies.set(name, value, domain=domain)
            conn.close()
        except Exception as e:
            print(f"Warning: Could not load Opera cookies: {e}")

    def _load_safari_cookies(self) -> None:
        """Load cookies from Safari profile (macOS only)."""
        # Safari is not natively available on Windows, but placeholder for cross-platform
        safari_cookies_path = Path.home() / "Library" / "Cookies" / "Cookies.binarycookies"
        if not safari_cookies_path.exists():
            print("Safari cookies not found (Safari is not available on Windows)")
            return
        print("Safari cookie extraction is not implemented on Windows.")
        # Implementing binarycookies parsing is non-trivial and not supported here.

    def _load_firefox_cookies(self) -> None:
        """Load cookies from Firefox profile."""
        firefox_profiles_path = Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"
        
        if not firefox_profiles_path.exists():
            # No Firefox cookies available, will proceed with unauthenticated session
            return

        # Find the most recent Firefox profile
        profiles = list(firefox_profiles_path.glob("*.default-release"))
        if not profiles:
            profiles = list(firefox_profiles_path.glob("*.default"))
        
        if not profiles:
            return

        cookies_db = profiles[0] / "cookies.sqlite"
        if not cookies_db.exists():
            return

        try:
            conn = sqlite3.connect(cookies_db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, value, domain FROM moz_cookies WHERE domain LIKE ?",
                (f"%{self.IMHENTAI_DOMAIN}%",)
            )
            
            for name, value, domain in cursor.fetchall():
                self.session.cookies.set(name, value, domain=domain)
            
            conn.close()
        except Exception as e:
            print(f"Warning: Could not load Firefox cookies: {e}")

    def _load_chrome_cookies(self) -> None:
        """Load cookies from Chrome profile."""
        chrome_cookies_path = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cookies"
        
        if not chrome_cookies_path.exists():
            return

        try:
            conn = sqlite3.connect(chrome_cookies_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, value, host_key FROM cookies WHERE host_key LIKE ?",
                (f"%{self.IMHENTAI_DOMAIN}%",)
            )
            
            for name, value, domain in cursor.fetchall():
                self.session.cookies.set(name, value, domain=domain)
            
            conn.close()
        except Exception as e:
            print(f"Warning: Could not load Chrome cookies: {e}")

    def get_session(self) -> requests.Session:
        """Get configured requests session."""
        return self.session

    def is_authenticated(self) -> bool:
        """Check if session has authentication cookies."""
        for cookie in self.session.cookies:
            if cookie.domain and self.IMHENTAI_DOMAIN in cookie.domain:
                return True
        return False

    def test_connection(self) -> bool:
        """Test connection to IMHentai and verify session works.
        
        Returns:
            True if connection and session are valid, False otherwise.
        """
        try:
            response = self.session.get(
                f"https://{self.IMHENTAI_DOMAIN}/",
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Warning: Connection test failed: {e}")
            return False
