"""Bounded, identified public reads. Never solve access challenges or scrape Facebook."""
import json
import math
import ipaddress
import socket
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import requests

USER_AGENT = 'CTFFinderPH/1.0 (Philippine CTF announcement index; daily collection)'


class FetchError(Exception):
    pass


class RateLimited(FetchError):
    """An unsuccessful request; the caller decides whether to retry later."""
    def __init__(self, retry_after=None):
        self.retry_after = retry_after
        super().__init__('HTTP 429' + (f'; retry after {retry_after} seconds' if retry_after is not None else ''))


def retry_seconds(value):
    """Parse Retry-After without trusting arbitrary server text as an instruction."""
    if not value:
        return None
    if value.strip().isdigit():
        return int(value.strip())
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo:
            return max(0, math.ceil((date - datetime.now(timezone.utc)).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        pass
    return None


class Client:
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.robots = {}
        self.last_request = {}
        self.delays = {}
        self.rate_limits = {}

    def discovered_page(self, url, allowed_hosts=None):
        """Public search/directory targets cannot address private services."""
        host = urlsplit(url).hostname
        if not host or host in ('rootcon.org', 'www.rootcon.org'):
            raise FetchError('Publisher policy excludes automated page reads')
        try:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError:
            raise FetchError('Public target DNS lookup failed') from None
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise FetchError('Discovered URL must resolve only to public addresses')
        return self.public_page(url, allowed_hosts=allowed_hosts)

    def _check_cooldown(self, host):
        remaining = self.rate_limits.get(host, 0) - time.monotonic()
        if remaining > 0:
            raise RateLimited(math.ceil(remaining))

    def _check_rate_limit(self, response, host):
        if response.status_code == 429:
            delay = retry_seconds(response.headers.get('Retry-After'))
            if delay is not None:
                self.rate_limits[host] = time.monotonic() + delay
            response.close()
            raise RateLimited(delay)

    def post_json(self, url, payload, *, headers=None):
        """Bounded anonymous API POST; never inherit credentials or follow redirects."""
        parsed = urlsplit(url)
        host = parsed.hostname
        if parsed.scheme not in ('http', 'https') or not host or parsed.username or parsed.password:
            raise FetchError('Unsupported anonymous API URL')
        if host in ('facebook.com', 'www.facebook.com', 'm.facebook.com', 'mbasic.facebook.com'):
            raise FetchError('Direct Facebook requests are disabled')
        supplied = headers or {}
        if any(key.lower() in ('authorization', 'proxy-authorization', 'cookie') for key in supplied):
            raise FetchError('Anonymous API requests cannot include credentials')
        wait = self.delays.get(host, 0.3) - (time.monotonic() - self.last_request.get(host, 0))
        if wait > 0:
            time.sleep(min(wait, 30))
        self.last_request[host] = time.monotonic()
        try:
            # A separate session avoids existing auth/cookies; trust_env=False
            # also prevents requests from reading .netrc or proxy credentials.
            with requests.Session() as session:
                session.trust_env = False
                session.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/json'})
                with session.post(url, json=payload, headers=supplied, timeout=(5, 15),
                                  allow_redirects=False, stream=True) as response:
                    if response.status_code == 429:
                        raise RateLimited(retry_seconds(response.headers.get('Retry-After')))
                    if 300 <= response.status_code < 400:
                        raise FetchError('API redirects are disabled')
                    if response.status_code >= 400:
                        raise FetchError(f'HTTP {response.status_code}')
                    data = bytearray()
                    for block in response.iter_content(65536):
                        data.extend(block)
                        if len(data) > 4_000_000:
                            raise FetchError('Response exceeds 4 MB limit')
            try:
                parsed = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                raise FetchError('API response is not valid JSON') from None
            if not isinstance(parsed, dict):
                raise FetchError('API response is not a JSON object')
            return parsed
        except requests.RequestException as exc:
            raise FetchError(type(exc).__name__) from None

    def read(self, url, *, params=None, headers=None, allowed_hosts=None):
        host = urlsplit(url).hostname
        if urlsplit(url).scheme not in ('http', 'https') or not host:
            raise FetchError('Unsupported URL')
        if host in ('facebook.com', 'www.facebook.com', 'm.facebook.com', 'mbasic.facebook.com'):
            raise FetchError('Facebook HTML fetching is disabled; use authorized APIs or search-only discovery')
        if allowed_hosts is not None and host not in allowed_hosts:
            raise FetchError('URL is outside the configured organizer hosts')
        self._check_cooldown(host)
        wait = self.delays.get(host, 0.3) - (time.monotonic() - self.last_request.get(host, 0))
        if wait > 0:
            time.sleep(min(wait, 30))
        self.last_request[host] = time.monotonic()
        try:
            # Public reads never reuse a server's session cookies or .netrc auth.
            self.session.cookies.clear()
            r = self.session.get(url, params=params, headers=headers, timeout=(5, 15), allow_redirects=False, stream=True)
            self._check_rate_limit(r, host)
            if 300 <= r.status_code < 400:
                target = urljoin(url, r.headers.get('Location', ''))
                r.close()
                # Follow only within configured hosts (including robots redirects).
                if target == url or urlsplit(target).hostname not in (allowed_hosts or [host]):
                    raise FetchError('Redirect outside configured hosts')
                return self.read_redirect(target, headers=headers, allowed_hosts=allowed_hosts or [host])
            if r.status_code >= 400:
                status = r.status_code
                r.close()
                raise FetchError(f'HTTP {status}')
            data = bytearray()
            for block in r.iter_content(65536):
                data.extend(block)
                if len(data) > 4_000_000:
                    r.close()
                    raise FetchError('Response exceeds 4 MB limit')
            r.close()
            return bytes(data)
        except requests.RequestException as exc:
            # Do not expose request objects, headers, tokens, or key-bearing URLs.
            raise FetchError(type(exc).__name__) from None

    def read_redirect(self, url, **kwargs):
        # One redirect maximum avoids loops and unbounded traversal.
        host = urlsplit(url).hostname
        self._check_cooldown(host)
        try:
            self.session.cookies.clear()
            r = self.session.get(url, headers=kwargs.get('headers'), timeout=(5, 15), allow_redirects=False)
            self._check_rate_limit(r, host)
            if r.status_code != 200:
                raise FetchError(f'HTTP {r.status_code} after redirect')
            if len(r.content) > 4_000_000:
                raise FetchError('Response exceeds 4 MB limit')
            return r.content
        except requests.RequestException as exc:
            raise FetchError(type(exc).__name__) from None

    def public_page(self, url, allowed_hosts=None):
        host = urlsplit(url).hostname
        if host not in self.robots:
            root = f'{urlsplit(url).scheme}://{urlsplit(url).netloc}/robots.txt'
            try:
                raw = self.read(root, allowed_hosts=allowed_hosts).decode('utf-8', errors='replace')
            except RateLimited:
                raise
            except FetchError as exc:
                if str(exc) not in ('HTTP 404', 'HTTP 410'):
                    raise FetchError(f'Cannot verify robots.txt: {exc}') from None
                raw = ''
            robot = RobotFileParser()
            robot.parse(raw.splitlines())
            self.robots[host] = robot
            delay = robot.crawl_delay(USER_AGENT) or robot.crawl_delay('*') or 0.3
            if delay > 30:
                raise FetchError('Crawl delay exceeds job budget; source needs a slower adapter')
            self.delays[host] = delay
        if not self.robots[host].can_fetch(USER_AGENT, url):
            raise FetchError('robots.txt disallows automated access')
        return self.read(url, allowed_hosts=allowed_hosts)
