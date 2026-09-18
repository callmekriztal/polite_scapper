import hashlib
import re
from typing import Optional
from urllib.parse import urljoin

RATING_MAP = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5
}

def make_absolute_url(base_url: str, relative_url: str) -> str:
    """Convert relative URL to absolute URL using urljoin."""
    return urljoin(base_url, relative_url)

def url_to_cache_filename(url: str) -> str:
    """Generate deterministic cache filename from URL."""
    # Catalogue pages
    catalogue_match = re.search(r"catalogue/page-(\d+)\.html", url)
    if catalogue_match:
        return f"catalogue-page-{catalogue_match.group(1)}.html"
    if url in ("https://books.toscrape.com/", "https://books.toscrape.com/index.html"):
        return "catalogue-page-1.html"
    
    # Detail pages
    slug_match = re.search(r"/catalogue/([^/]+)/index\.html", url)
    if slug_match:
        slug = slug_match.group(1)
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
        return f"detail-{slug[:30]}-{url_hash}.html"
    
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    return f"detail-{url_hash}.html"

def normalize_price(price_text: str) -> float:
    """Extract float value from price string (e.g. '£51.77' -> 51.77)."""
    if not price_text:
        raise ValueError("Price text is empty")
    match = re.search(r"(\d+\.\d+|\d+)", price_text)
    if match:
        return float(match.group(1))
    raise ValueError(f"Could not parse numeric price from '{price_text}'")

def normalize_rating(rating_text: str) -> int:
    """Convert textual rating ('One', 'Two', 'Three', 'Four', 'Five') to integer 1-5."""
    if not rating_text:
        return 0
    clean = rating_text.strip().lower()
    return RATING_MAP.get(clean, 0)

def normalize_availability(availability_text: str) -> dict:
    """Parse raw availability text like 'In stock (22 available)' into structured format."""
    if not availability_text:
        return {"in_stock": False, "quantity": 0, "raw": ""}
    
    clean = clean_text(availability_text) or ""
    in_stock = "in stock" in clean.lower()
    quantity_match = re.search(r"\((\d+)\s+available\)", clean, re.IGNORECASE)
    quantity = int(quantity_match.group(1)) if quantity_match else (1 if in_stock else 0)
    
    return {
        "in_stock": in_stock,
        "quantity": quantity,
        "raw": clean
    }

def clean_text(text: Optional[str]) -> Optional[str]:
    """Clean whitespace and newlines from scraped text."""
    if text is None:
        return None
    cleaned = " ".join(text.strip().split())
    return cleaned if cleaned else None
