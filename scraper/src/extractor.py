from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from src.config import Config
from src.fetcher import Fetcher
from src.utils import (
    clean_text,
    normalize_availability,
    normalize_price,
    normalize_rating
)

class BookExtractor:
    """Extracts raw and normalized product data from book detail pages."""

    def __init__(self, config: Config, fetcher: Fetcher):
        self.config = config
        self.fetcher = fetcher

    def extract_book(self, product_url: str, source_page: str) -> dict:
        """
        Fetch book detail page and extract fields.
        Raises Exception if page retrieval or parsing fails.
        """
        # Simulation hook for broken test URL
        if self.config.BROKEN_TEST_URL and product_url == self.config.BROKEN_TEST_URL:
            raise requests.HTTPError(f"Simulated broken page error for {product_url}")

        fetched_at = datetime.now(timezone.utc).isoformat()
        html_content, _ = self.fetcher.fetch(product_url)
        soup = BeautifulSoup(html_content, "html.parser")

        # Specific selector for product main area
        product_main = soup.select_one("div.product_main")
        if not product_main:
            raise ValueError(f"Could not find product_main area in {product_url}")

        # Title
        h1_tag = product_main.select_one("h1")
        title_raw = h1_tag.get_text() if h1_tag else ""
        title = clean_text(title_raw) or ""

        # Price text
        price_tag = product_main.select_one("p.price_color")
        price_text = clean_text(price_tag.get_text()) if price_tag else ""

        # Availability text
        avail_tag = product_main.select_one("p.instock.availability")
        availability_text = clean_text(avail_tag.get_text()) if avail_tag else ""

        # Rating text
        rating_tag = product_main.select_one("p.star-rating")
        rating_text = ""
        if rating_tag:
            classes = rating_tag.get("class", [])
            for c in classes:
                if c.lower() != "star-rating":
                    rating_text = c
                    break

        # Description (located after #product_description div header if present)
        desc_header = soup.select_one("#product_description")
        description = None
        if desc_header:
            desc_p = desc_header.find_next_sibling("p")
            if desc_p:
                description = clean_text(desc_p.get_text())

        # Construct raw record
        raw_record = {
            "title": title,
            "product_url": product_url,
            "price_text": price_text,
            "availability_text": availability_text,
            "rating_text": rating_text,
            "description": description,
            "source_page": source_page,
            "fetched_at": fetched_at,
        }

        # Normalize fields (Stage 4)
        price_gbp = normalize_price(price_text)
        rating_int = normalize_rating(rating_text)
        availability_norm = normalize_availability(availability_text)

        raw_record.update({
            "price_gbp": price_gbp,
            "rating_int": rating_int,
            "availability_normalized": availability_norm
        })

        return raw_record
