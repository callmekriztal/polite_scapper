import time
from urllib.robotparser import RobotFileParser

import requests

from polite_scraper import ui
from polite_scraper.config import Config
from polite_scraper.utils import url_to_cache_filename


class Fetcher:
    """HTTP fetcher with polite rate-limiting, status checking, and HTML disk caching."""

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config.USER_AGENT
        })
        self.cache_hits = 0
        self.network_fetches = 0
        self.last_request_time = 0.0

    def fetch(self, url: str, force_refresh: bool = False) -> tuple[str, bool]:
        """
        Fetch HTML from URL or cache.
        Returns tuple of (html_content, was_cached).
        Raises requests.HTTPError if response status != 200.
        """
        force_refresh = force_refresh or self.config.FORCE_REFRESH
        self.config.ensure_directories()
        cache_filename = url_to_cache_filename(url)
        cache_path = self.config.CACHE_DIR / cache_filename

        # Check local cache first unless force_refresh is True
        if not force_refresh and cache_path.is_file():
            try:
                html_content = cache_path.read_text(encoding="utf-8")
                self.cache_hits += 1
                size_bytes = len(html_content.encode("utf-8"))
                ui.debug(f"CACHE HIT  {url} ({size_bytes} bytes)")
                return html_content, True
            except Exception as e:
                ui.debug(f"Cache read error for {cache_path}: {e}. Falling back to network fetch.")

        html_content = self._network_get(url)
        cache_path.write_text(html_content, encoding="utf-8")
        return html_content, False

    def fetch_robots_txt(self, base_url: str) -> RobotFileParser | None:
        """
        Fetch robots.txt for a site. Returns a parser, or None if no robots.txt
        exists / it cannot be fetched (treated as "no rules").
        """
        robots_url = base_url.rstrip("/") + "/robots.txt"
        try:
            response = self.session.get(robots_url, timeout=self.config.TIMEOUT)
        except requests.RequestException as e:
            ui.debug(f"robots.txt fetch failed for {robots_url}: {e}")
            return None
        if response.status_code != 200:
            ui.debug(f"robots.txt not available ({response.status_code}) at {robots_url}")
            return None

        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser

    def _network_get(self, url: str) -> str:
        # Respect rate limit of at least MIN_DELAY_SECONDS between network requests
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.config.MIN_DELAY_SECONDS:
            time_to_sleep = self.config.MIN_DELAY_SECONDS - elapsed
            time.sleep(time_to_sleep)

        # Make network request
        ui.debug(f"FETCH      {url} ...")
        self.last_request_time = time.time()
        response = self.session.get(url, timeout=self.config.TIMEOUT)
        response.encoding = "utf-8"  # Ensure proper UTF-8 decoding for currency symbols
        self.network_fetches += 1

        # Only treat HTTP 200 as successful per Stage 1 requirement
        if response.status_code != 200:
            raise requests.HTTPError(
                f"HTTP fetch failed for {url} with status code {response.status_code}",
                response=response
            )

        html_content = response.text
        size_bytes = len(html_content.encode("utf-8"))
        ui.debug(f"FETCH OK   {url} ({size_bytes} bytes)")
        return html_content
