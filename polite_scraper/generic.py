"""Generic site scraper.

Works on any website: BFS-crawls same-domain links (rate-limited and
robots.txt-checked) and extracts useful page metadata from each page.
"""

from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from polite_scraper import ui
from polite_scraper.config import Config
from polite_scraper.fetcher import Fetcher
from polite_scraper.utils import clean_text, make_absolute_url


class GenericExtractor:
    """Extracts page metadata from arbitrary HTML."""

    HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]

    def extract_page(self, page_url: str, html_content: str) -> dict:
        soup = BeautifulSoup(html_content, "html.parser")

        # Title: <title> falls back to first <h1>
        title = clean_text(soup.title.get_text()) if soup.title else None
        if not title:
            h1 = soup.find("h1")
            title = clean_text(h1.get_text()) if h1 else ""

        # First H1
        h1 = soup.find("h1")
        h1_text = clean_text(h1.get_text()) if h1 else None

        # Meta description
        meta_desc = None
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and meta_tag.get("content"):
            meta_desc = clean_text(meta_tag["content"])

        # Headings (up to 10, non-empty)
        headings = []
        for tag in soup.find_all(self.HEADING_TAGS):
            text = clean_text(tag.get_text())
            if text:
                headings.append(text)
            if len(headings) >= 10:
                break

        # Same-domain links
        origin = urlparse(page_url)
        same_links = []
        for a in soup.find_all("a", href=True):
            abs_url = make_absolute_url(page_url, a["href"])
            parsed = urlparse(abs_url)
            if parsed.netloc == origin.netloc and parsed.scheme in ("http", "https"):
                same_links.append(abs_url.split("#")[0])
        unique_links = list(dict.fromkeys(same_links))

        # Word count of visible-ish text
        for junk in soup(["script", "style", "noscript"]):
            junk.decompose()
        body_text = soup.get_text(separator=" ", strip=True)
        word_count = len(body_text.split())

        return {
            "url": page_url,
            "title": title or "",
            "h1": h1_text,
            "meta_description": meta_desc,
            "headings": headings,
            "same_domain_links": unique_links[:50],
            "link_count": len(unique_links),
            "image_count": len(soup.find_all("img")),
            "word_count": word_count,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


class GenericSiteScraper:
    """BFS crawler + extractor for arbitrary websites."""

    def __init__(self, config: Config, fetcher: Fetcher, extractor: GenericExtractor | None = None):
        self.config = config
        self.fetcher = fetcher
        self.extractor = extractor or GenericExtractor()
        self.robots_parser = None

    def check_robots(self, start_url: str) -> bool:
        """Politeness check: consult robots.txt for our User-Agent. Returns True if allowed."""
        base = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
        self.robots_parser = self.fetcher.fetch_robots_txt(base)
        if self.robots_parser is None:
            ui.info("robots.txt: not available (no rules) — proceeding politely anyway")
            return True
        allowed = self.robots_parser.can_fetch(self.config.USER_AGENT, start_url)
        if allowed:
            ui.success("robots.txt: crawl allowed for our User-Agent")
        else:
            ui.error("robots.txt disallows scraping this URL for our User-Agent — aborting")
        return allowed

    def scrape(self) -> tuple[list[dict], list[dict]]:
        """Returns (raw_page_records, error_records)."""
        start_url = self.config.START_URL
        max_pages = self.config.MAX_CATALOGUE_PAGES
        max_links = self.config.MAX_LINKS_PER_PAGE

        raw_records: list[dict] = []
        error_records: list[dict] = []

        queue: deque[str] = deque([start_url])
        seen: set[str] = {start_url.split("#")[0]}
        pages_fetched = 0

        while queue and pages_fetched < max_pages:
            url = queue.popleft()

            try:
                html_content, _ = self.fetcher.fetch(url)
            except Exception as ex:
                error_records.append({"url": url, "reason": f"Fetch failed: {ex}"})
                continue

            pages_fetched += 1
            raw = self.extractor.extract_page(url, html_content)

            if not raw["title"]:
                error_records.append({
                    "url": url,
                    "reason": "No page title found (skipped record)",
                    "raw_record": raw,
                })
            else:
                raw_records.append(raw)

            # Enqueue new same-domain links (up to max_links per page)
            for link in raw["same_domain_links"]:
                if pages_fetched + len(queue) >= max_pages and len(queue) >= max_links:
                    break
                if link not in seen:
                    seen.add(link)
                    if self._robots_allows(link):
                        queue.append(link)

        return raw_records, error_records

    def _robots_allows(self, url: str) -> bool:
        if self.robots_parser is None:
            return True
        return self.robots_parser.can_fetch(self.config.USER_AGENT, url)
