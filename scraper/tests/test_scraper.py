import sys
from pathlib import Path

# Ensure scraper root is in python path for tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.config import Config
from src.crawler import CatalogueCrawler
from src.extractor import BookExtractor
from src.fetcher import Fetcher
from src.utils import normalize_price, normalize_rating, clean_text
from src.validator import RecordValidator

def test_price_normalization():
    assert normalize_price("£51.77") == 51.77
    assert normalize_price("£ 19.99") == 19.99
    assert normalize_price("100") == 100.0
    with pytest.raises(ValueError):
        normalize_price("Price unavailable")

def test_rating_normalization():
    assert normalize_rating("One") == 1
    assert normalize_rating("Three") == 3
    assert normalize_rating("Five") == 5
    assert normalize_rating("invalid") == 0

def test_missing_description_becomes_none():
    assert clean_text(None) is None
    assert clean_text("") is None
    assert clean_text("   ") is None
    assert clean_text(" Valid text ") == "Valid text"

def test_invalid_record_validation():
    # Invalid title and invalid negative price
    invalid_raw = {
        "title": "",  # invalid
        "product_url": "https://books.toscrape.com/catalogue/test_1/index.html",
        "price_text": "£-10",
        "price_gbp": -10.0,  # invalid
        "availability_text": "In stock",
        "rating_text": "One",
        "description": None,
        "source_page": "https://books.toscrape.com/catalogue/page-1.html",
        "fetched_at": "2026-09-18T10:00:00+00:00"
    }
    validated, error = RecordValidator.validate_record(invalid_raw)
    assert validated is None
    assert error is not None
    assert error["product_url"] == invalid_raw["product_url"]

def test_broken_detail_page_simulation(tmp_path):
    config = Config()
    config.CACHE_DIR = tmp_path / "cache"
    config.OUTPUT_DIR = tmp_path / "output"
    
    broken_url = "https://books.toscrape.com/catalogue/broken-book_999/index.html"
    config.BROKEN_TEST_URL = broken_url
    
    fetcher = Fetcher(config)
    extractor = BookExtractor(config, fetcher)

    with pytest.raises(Exception) as exc_info:
        extractor.extract_book(broken_url, "https://books.toscrape.com/catalogue/page-1.html")
    
    assert "Simulated broken page error" in str(exc_info.value)


def test_generic_extractor_basic_page():
    from src.generic import GenericExtractor

    html = """
    <html>
      <head><title>My Site</title><meta name="description" content="A demo site"></head>
      <body>
        <h1> Welcome </h1>
        <h2>Section</h2>
        <a href="/about">About</a>
        <a href="https://example.org/external">External</a>
        <img src="x.png">
        <p>hello world some words here</p>
      </body>
    </html>
    """
    raw = GenericExtractor().extract_page("https://example.com/", html)
    assert raw["title"] == "My Site"
    assert raw["h1"] == "Welcome"
    assert raw["meta_description"] == "A demo site"
    assert "https://example.com/about" in raw["same_domain_links"]
    assert all("example.org" not in l for l in raw["same_domain_links"])
    assert raw["image_count"] == 1
    assert raw["word_count"] >= 5


def test_generic_page_validation_rejects_empty_title():
    from src.validator import RecordValidator

    raw = {
        "url": "https://example.com/",
        "title": "",
        "h1": None,
        "meta_description": None,
        "headings": [],
        "same_domain_links": [],
        "link_count": 0,
        "image_count": 0,
        "word_count": 0,
        "fetched_at": "2026-09-18T10:00:00+00:00",
    }
    validated, error = RecordValidator.validate_page(raw)
    assert validated is None
    assert error is not None
    assert error["product_url"] == raw["url"]


def test_cli_build_config():
    import argparse
    from src.cli import build_config, build_parser

    parser = build_parser()
    args = parser.parse_args(["example.com", "--pages", "5", "--max-links", "12",
                              "--delay", "1.5", "--force"])
    config = build_config(args)
    assert config.BASE_URL == "https://example.com/"
    assert config.MAX_CATALOGUE_PAGES == 5
    assert config.MAX_LINKS_PER_PAGE == 12
    assert config.MIN_DELAY_SECONDS == 1.5
    assert config.FORCE_REFRESH is True
