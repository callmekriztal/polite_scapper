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
