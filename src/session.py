"""Session management and browser cookie extraction for IMHentai."""

import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import getpass
import sys


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
        # Default cookie store file next to the tool directory
        self._cookie_store = Path(__file__).resolve().parents[1] / 'imhentai_cookies.json'
        # Try loading saved cookies first (persisted from prior login)
        if not self._load_cookies_from_store():
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
                # Copy DB to avoid locks
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.close()
                shutil.copy(str(cookies_db), tmp.name)
                conn = sqlite3.connect(tmp.name)
                cursor = conn.cursor()

                # Determine available columns in moz_cookies
                cursor.execute("PRAGMA table_info(moz_cookies)")
                cols = [r[1] for r in cursor.fetchall()]
                name_col = 'name' if 'name' in cols else None
                value_col = 'value' if 'value' in cols else None
                domain_col = None
                for dc in ('host', 'domain', 'baseDomain'):
                    if dc in cols:
                        domain_col = dc
                        break

                if not (name_col and value_col and domain_col):
                    conn.close()
                    os.unlink(tmp.name)
                    return

                query = f"SELECT {name_col}, {value_col}, {domain_col} FROM moz_cookies WHERE {domain_col} LIKE ?"
                cursor.execute(query, (f"%{self.IMHENTAI_DOMAIN}%",))

                for name, value, domain in cursor.fetchall():
                    try:
                        self.session.cookies.set(name, value, domain=domain)
                    except Exception:
                        continue

                conn.close()
                os.unlink(tmp.name)
            except Exception as e:
                print(f"Warning: Could not load Firefox cookies: {e}")

    def _load_chrome_cookies(self) -> None:
        """Load cookies from Chrome profile."""
        chrome_cookies_path = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cookies"
        
        if not chrome_cookies_path.exists():
            return

            try:
                # Copy DB to temp to avoid lock errors
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.close()
                shutil.copy(str(chrome_cookies_path), tmp.name)
                conn = sqlite3.connect(tmp.name)
                cursor = conn.cursor()

                # Inspect columns
                cursor.execute("PRAGMA table_info(cookies)")
                cols = [r[1] for r in cursor.fetchall()]
                if 'name' in cols and 'host_key' in cols:
                    name_col = 'name'
                    domain_col = 'host_key'
                elif 'name' in cols and 'host' in cols:
                    name_col = 'name'
                    domain_col = 'host'
                else:
                    conn.close()
                    os.unlink(tmp.name)
                    return

                value_col = 'value' if 'value' in cols else ('encrypted_value' if 'encrypted_value' in cols else None)
                if not value_col:
                    conn.close()
                    os.unlink(tmp.name)
                    return

                query = f"SELECT {name_col}, {value_col}, {domain_col} FROM cookies WHERE {domain_col} LIKE ?"
                cursor.execute(query, (f"%{self.IMHENTAI_DOMAIN}%",))

                for name, value, domain in cursor.fetchall():
                    if value_col == 'value' and value:
                        self.session.cookies.set(name, value, domain=domain)
                    elif value_col == 'encrypted_value' and value:
                        # Try to decrypt on Windows using win32crypt
                        decrypted = None
                        if win32crypt is not None:
                            try:
                                decrypted = win32crypt.CryptUnprotectData(value, None, None, None, 0)[1].decode('utf-8')
                            except Exception:
                                decrypted = None

                        if decrypted:
                            self.session.cookies.set(name, decrypted, domain=domain)

                conn.close()
                os.unlink(tmp.name)
            except Exception as e:
                print(f"Warning: Could not load Chrome cookies: {e}")


    def get_session(self) -> requests.Session:
        """Get configured requests session."""
        return self.session

    def _load_cookies_from_store(self) -> bool:
        """Load cookies from persistent JSON store if available.

        Returns True if cookies were loaded and set, False otherwise.
        """
        try:
            if not self._cookie_store.exists():
                return False
            data = json.loads(self._cookie_store.read_text(encoding='utf-8'))
            loaded = False
            for c in data.get('cookies', []):
                if c.get('domain') and self.IMHENTAI_DOMAIN in c.get('domain'):
                    self.session.cookies.set(c.get('name'), c.get('value'), domain=c.get('domain'), path=c.get('path', '/'))
                    loaded = True
            return loaded
        except Exception:
            return False

    def save_cookies_to_store(self) -> None:
        """Persist cookies for IMHentai domain to the JSON cookie store."""
        try:
            cookies = []
            for cookie in self.session.cookies:
                try:
                    if cookie.domain and self.IMHENTAI_DOMAIN in cookie.domain:
                        cookies.append({
                            'name': cookie.name,
                            'value': cookie.value,
                            'domain': cookie.domain,
                            'path': cookie.path,
                            'expires': cookie.expires,
                            'secure': cookie.secure,
                            'httpOnly': getattr(cookie, 'rest', {}).get('HttpOnly', False)
                        })
                except Exception:
                    continue

            payload = {'cookies': cookies}
            self._cookie_store.write_text(json.dumps(payload), encoding='utf-8')
        except Exception:
            # Best-effort save; ignore failures
            pass

    def is_authenticated(self) -> bool:
        """Check if session has authentication cookies."""
        for cookie in self.session.cookies:
            if cookie.domain and self.IMHENTAI_DOMAIN in cookie.domain:
                return True
        return False

    def login(self, username: str, password: str) -> bool:
        """Attempt to log in using provided credentials.

        Tries a couple of known login endpoints and treats any resulting
        change to authenticated cookies or a successful connection as success.
        """
        # Emulate a browser login flow: GET a login page to extract CSRF-like tokens
        login_pages = [
            urljoin(f"https://{self.IMHENTAI_DOMAIN}", '/login/'),
            urljoin(f"https://{self.IMHENTAI_DOMAIN}", '/'),
        ]

        # Candidate POST endpoint(s)
        candidate_posts = [
            urljoin(f"https://{self.IMHENTAI_DOMAIN}", '/inc/login.php'),
            urljoin(f"https://{self.IMHENTAI_DOMAIN}", '/login/'),
        ]

        # Common credential field name templates
        payload_templates = [
            {'username': username, 'password': password},
            {'user': username, 'pass': password},
            {'login': username, 'password': password},
        ]

        headers = {
            'Origin': f'https://{self.IMHENTAI_DOMAIN}',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': self.session.headers.get('User-Agent')
        }

        for page in login_pages:
            try:
                r = self.session.get(page, timeout=15)
            except Exception:
                continue

            if r.status_code != 200:
                continue

            try:
                soup = BeautifulSoup(r.text, 'lxml')
            except Exception:
                soup = BeautifulSoup(r.text, 'html.parser')

            # Extract candidate tokens from meta tags and hidden inputs
            tokens: Dict[str, str] = {}
            for m in soup.find_all('meta'):
                name = (m.get('name') or '').strip()
                prop = (m.get('property') or '').strip()
                content = m.get('content')
                if content and (('csrf' in name.lower()) or ('csrf' in prop.lower()) or ('token' in name.lower()) or ('token' in prop.lower())):
                    tokens[name or prop] = content

            for inp in soup.find_all('input', {'type': 'hidden'}):
                in_name = inp.get('name')
                if not in_name:
                    continue
                if any(k in in_name.lower() for k in ('csrf', 'token', 'auth')):
                    tokens[in_name] = inp.get('value', '')

            # Also try to find the login form action if present
            form_action = None
            form = soup.find('form')
            if form and form.get('action'):
                form_action = form.get('action')
                if form_action.startswith('/'):
                    form_action = urljoin(f"https://{self.IMHENTAI_DOMAIN}", form_action)

            # Try POSTing to candidate endpoints (prefer discovered form action)
            post_targets = []
            if form_action:
                post_targets.append(form_action)
            post_targets.extend(candidate_posts)

            for target in post_targets:
                for tmpl in payload_templates:
                    data = dict(tmpl)
                    # merge tokens into payload (don't overwrite existing keys)
                    for k, v in tokens.items():
                        if k and k not in data:
                            data[k] = v

                    try:
                        resp = self.session.post(target, data=data, headers={**headers, 'Referer': page}, timeout=15, allow_redirects=True)
                    except Exception:
                        continue

                    # If the site set auth cookies, we're done
                    if self.is_authenticated():
                        return True

                    # Some endpoints reply with 'success' or similar markers
                    try:
                        text = (resp.text or '').lower()
                        if 'success' in text and resp.status_code in (200, 302):
                            return True
                    except Exception:
                        pass

        # Fallback: try direct POSTs without tokens
        for ep in candidate_posts:
            try:
                resp = self.session.post(ep, data={'username': username, 'password': password}, headers=headers, timeout=15, allow_redirects=True)
            except Exception:
                continue
            if self.is_authenticated():
                return True
            try:
                if 'success' in (resp.text or '').lower():
                    return True
            except Exception:
                pass

        return False

    def ensure_authenticated(self, interactive: bool = True, max_attempts: int = 3) -> bool:
        """Ensure we have an authenticated session.

        If not authenticated and `interactive` is True, prompt for credentials
        and attempt login up to `max_attempts` times.
        """
        if self.is_authenticated():
            return True

        if not interactive:
            return False

        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            try:
                user = input('IMHentai username: ').strip()
                pwd = getpass.getpass('IMHentai password: ')
            except (KeyboardInterrupt, EOFError):
                print('\nLogin cancelled')
                return False

            ok = self.login(user, pwd)
            if ok:
                return True
            print('Login failed, please try again.')

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
