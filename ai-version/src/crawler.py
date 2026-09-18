from bs4 import BeautifulSoup
from src.config import Config
from src.fetcher import Fetcher
from src.utils import make_absolute_url

class DiscoveryResult:
    def __init__(self, catalogue_pages_count: int, discovered_count: int, book_urls: list[dict]):
        self.catalogue_pages_count = catalogue_pages_count
        self.discovered_count = discovered_count
        self.book_urls = book_urls  # List of dicts: {"product_url": ..., "source_page": ...}

class CatalogueCrawler:
    """Discovers book URLs by crawling catalogue pagination."""

    def __init__(self, config: Config, fetcher: Fetcher):
        self.config = config
        self.fetcher = fetcher

    def discover_books(self) -> DiscoveryResult:
        current_url = self.config.START_URL
        pages_processed = 0
        discovered_entries = []
        seen_urls = set()

        while current_url and pages_processed < self.config.MAX_CATALOGUE_PAGES:
            html_content, _ = self.fetcher.fetch(current_url)
            pages_processed += 1

            soup = BeautifulSoup(html_content, "html.parser")
            
            # Find all product links in the current catalogue page
            # Each book card is in an <article class="product_pod">
            product_pods = soup.select("article.product_pod")
            for pod in product_pods:
                a_tag = pod.select_one("h3 a")
                if a_tag and a_tag.get("href"):
                    rel_url = a_tag["href"]
                    abs_url = make_absolute_url(current_url, rel_url)
                    
                    if abs_url not in seen_urls:
                        seen_urls.add(abs_url)
                        discovered_entries.append({
                            "product_url": abs_url,
                            "source_page": current_url
                        })

            # Check for "next" page link
            next_li = soup.select_one("li.next a")
            if next_li and next_li.get("href"):
                next_rel = next_li["href"]
                current_url = make_absolute_url(current_url, next_rel)
            else:
                current_url = None

        return DiscoveryResult(
            catalogue_pages_count=pages_processed,
            discovered_count=len(discovered_entries),
            book_urls=discovered_entries
        )
