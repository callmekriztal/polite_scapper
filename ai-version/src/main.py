import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add src package directory to Python path if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.crawler import CatalogueCrawler
from src.extractor import BookExtractor
from src.fetcher import Fetcher
from src.reporter import Reporter, RunMetrics
from src.validator import RecordValidator

def run_scraper() -> dict:
    start_time = time.time()
    run_timestamp = datetime.now(timezone.utc).isoformat()
    
    config = Config()
    config.ensure_directories()
    
    fetcher = Fetcher(config)
    crawler = CatalogueCrawler(config, fetcher)
    extractor = BookExtractor(config, fetcher)
    reporter = Reporter(config)

    print("==================================================")
    print("STAGE 0 & 1 & 2: DISCOVERING CATALOGUE PAGES")
    print("==================================================")
    discovery = crawler.discover_books()
    
    print("\n--- STAGE 2 CHECKPOINT ---")
    print(f"catalogue_pages={discovery.catalogue_pages_count}")
    print(f"discovered={discovery.discovered_count}")
    print(f"unique_urls={len(discovery.book_urls)}")
    print("---------------------------\n")

    print("==================================================")
    print("STAGE 3, 4 & 5: EXTRACTING & VALIDATING BOOK DETAILS")
    print("==================================================")
    
    validated_records = []
    error_records = []
    broken_pages_count = 0
    checkpoint_printed = False

    for idx, entry in enumerate(discovery.book_urls, 1):
        product_url = entry["product_url"]
        source_page = entry["source_page"]

        try:
            raw_record = extractor.extract_book(product_url, source_page)
            
            # Print raw record checkpoint once
            if not checkpoint_printed:
                print("\n--- STAGE 3 RAW RECORD CHECKPOINT ---")
                checkpoint_data = {
                    "title": raw_record["title"],
                    "product_url": raw_record["product_url"],
                    "price_text": raw_record["price_text"],
                    "availability_text": raw_record["availability_text"],
                    "rating_text": raw_record["rating_text"],
                    "description": raw_record["description"],
                    "source_page": raw_record["source_page"],
                    "fetched_at": raw_record["fetched_at"]
                }
                print(json.dumps(checkpoint_data, indent=2))
                print("------------------------------------\n")
                checkpoint_printed = True

            # Validate record (Stage 5)
            validated, error_info = RecordValidator.validate_record(raw_record)
            if validated:
                validated_records.append(validated)
            else:
                error_records.append(error_info)

        except Exception as ex:
            broken_pages_count += 1
            print(f"ERROR processing detail page {product_url}: {ex}")
            error_records.append({
                "product_url": product_url,
                "reason": f"Page processing exception: {str(ex)}",
                "raw_record": None
            })

    detail_pages_attempted = len(discovery.book_urls)
    print(f"\ndetail_pages={detail_pages_attempted}")

    print("\n==================================================")
    print("STAGE 6: STORING RESULTS AND GENERATING REPORT")
    print("==================================================")
    
    reporter.save_books(validated_records)
    reporter.save_errors(error_records)
    
    end_time = time.time()
    duration = round(end_time - start_time, 3)

    metrics = RunMetrics(
        run_timestamp=run_timestamp,
        duration_seconds=duration,
        catalogue_pages=discovery.catalogue_pages_count,
        discovered_urls=discovery.discovered_count,
        unique_urls=len(discovery.book_urls),
        detail_pages=detail_pages_attempted,
        successful_records=len(validated_records),
        failed_records=len(error_records),
        cache_hits=fetcher.cache_hits,
        network_fetches=fetcher.network_fetches,
        broken_pages=broken_pages_count,
        output_record_count=len(validated_records)
    )
    
    reporter.save_report(metrics)

    print("\n==================================================")
    print("FINAL SUMMARY CHECKPOINTS")
    print("==================================================")
    print(f"catalogue_pages: {metrics.catalogue_pages}")
    print(f"discovered_urls: {metrics.discovered_urls}")
    print(f"unique_urls:     {metrics.unique_urls}")
    print(f"detail_pages:    {metrics.detail_pages}")
    print(f"validated_books: {metrics.successful_records}")
    print(f"failed_records:  {metrics.failed_records}")
    print(f"cache_hits:      {metrics.cache_hits}")
    print(f"network_fetches: {metrics.network_fetches}")
    print(f"duration:        {metrics.duration_seconds}s")
    print("==================================================")

    return {
        "metrics": metrics,
        "validated_records": validated_records,
        "error_records": error_records
    }

if __name__ == "__main__":
    run_scraper()
