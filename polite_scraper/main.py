import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Allow running as a plain script: python polite_scraper/main.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polite_scraper import cli, ui
from polite_scraper.config import Config
from polite_scraper.crawler import CatalogueCrawler
from polite_scraper.extractor import BookExtractor
from polite_scraper.fetcher import Fetcher
from polite_scraper.generic import GenericSiteScraper
from polite_scraper.reporter import Reporter, RunMetrics
from polite_scraper.validator import RecordValidator


def resolve_mode_and_start(config: Config, fetcher: Fetcher, requested_mode: str) -> tuple[str, str]:
    """
    Determine the effective mode and the crawl start URL.
    - 'book': uses the catalogue start page (special-cased for books.toscrape.com)
    - 'generic': crawls the given URL as-is
    - 'auto': probes the page for book-catalogue markup, falls back to generic
    Returns (mode, start_url).
    """
    given_url = config.BASE_URL
    path = urlparse(given_url).path
    is_toscrape_root = "books.toscrape.com" in given_url and path in ("", "/")
    book_start = config.toscrape_start_url() if is_toscrape_root else given_url

    if requested_mode == "book":
        return "book", book_start
    if requested_mode == "generic":
        return "generic", given_url

    # auto: probe for book-catalogue markup
    try:
        html, _ = fetcher.fetch(book_start)
    except requests.RequestException as ex:
        ui.error(f"Could not reach {book_start}: {ex}")
        raise SystemExit(1)

    soup = BeautifulSoup(html, "html.parser")
    looks_like_book_catalogue = bool(soup.select("article.product_pod"))
    return ("book", book_start) if looks_like_book_catalogue else ("generic", given_url)


def run_book_mode(config: Config, fetcher: Fetcher, reporter: Reporter) -> tuple[list, list, dict]:
    """Crawl catalogue pages, extract & validate books. Returns (validated, errors, info)."""
    crawler = CatalogueCrawler(config, fetcher)
    extractor = BookExtractor(config, fetcher)

    ui.stage("Discovering catalogue pages")
    with ui.make_progress() as progress:
        progress.add_task("Crawling catalogue...", total=None)
        discovery = crawler.discover_books()

    ui.success(
        f"{discovery.catalogue_pages_count} catalogue pages crawled — "
        f"{len(discovery.book_urls)} unique book URLs"
    )
    ui.checkpoint("Discovery", {
        "catalogue_pages": discovery.catalogue_pages_count,
        "unique_urls": len(discovery.book_urls),
    })

    ui.stage("Extracting & validating book details")
    validated_records, error_records = [], []
    broken_pages = 0
    checkpoint_shown = False

    with ui.make_progress() as progress:
        task = progress.add_task("Extracting books...", total=len(discovery.book_urls))
        for entry in discovery.book_urls:
            product_url, source_page = entry["product_url"], entry["source_page"]
            try:
                raw_record = extractor.extract_book(product_url, source_page)

                if not checkpoint_shown:
                    ui.checkpoint("Raw Record Sample", {
                        k: raw_record[k] for k in (
                            "title", "product_url", "price_text",
                            "availability_text", "rating_text", "description", "fetched_at",
                        )
                    })
                    checkpoint_shown = True

                validated, error_info = RecordValidator.validate_record(raw_record)
                if validated:
                    validated_records.append(validated)
                else:
                    error_records.append(error_info)
            except Exception as ex:
                broken_pages += 1
                ui.debug(f"ERROR processing {product_url}: {ex}")
                error_records.append({
                    "product_url": product_url,
                    "reason": f"Page processing exception: {ex}",
                    "raw_record": None,
                })
            finally:
                progress.advance(task)

    ui.success(f"{len(validated_records)} valid books, {len(error_records)} rejected")
    return validated_records, error_records, {"broken_pages": broken_pages}


def run_generic_mode(config: Config, fetcher: Fetcher, reporter: Reporter) -> tuple[list, list, dict]:
    """BFS-crawl any site and extract page metadata. Returns (validated, errors, info)."""
    scraper = GenericSiteScraper(config, fetcher)

    if not scraper.check_robots(config.START_URL):
        ui.error("Aborting: robots.txt disallows this target")
        raise SystemExit(1)

    ui.stage("Crawling & extracting pages")
    with ui.make_progress() as progress:
        progress.add_task("Crawling site...", total=None)
        raw_records, error_records = scraper.scrape()

    ui.success(f"{len(raw_records)} pages extracted, {len(error_records)} skipped/failed")
    ui.checkpoint("Raw Page Sample", raw_records[0] if raw_records else {"note": "no pages"})

    validated_records = []
    for raw in raw_records:
        validated, error_info = RecordValidator.validate_page(raw)
        if validated:
            validated_records.append(validated)
        else:
            error_records.append(error_info)

    return validated_records, error_records, {"broken_pages": 0}


def run(args) -> int:
    ui.set_verbose(args.verbose)
    if not cli.ensure_url_provided(args):
        return 2

    config = cli.build_config(args)
    run_dir = cli.resolve_output_dir(config, args.name)
    config.OUTPUT_DIR = run_dir
    config.ensure_directories()

    fetcher = Fetcher(config)
    reporter = Reporter(config)

    mode, config.START_URL = resolve_mode_and_start(config, fetcher, args.mode)

    ui.banner(
        target_url=config.BASE_URL,
        mode=mode,
        pages=config.MAX_CATALOGUE_PAGES,
        delay=config.MIN_DELAY_SECONDS,
        cache_dir=str(config.CACHE_DIR),
        run_dir=str(run_dir.relative_to(config.BASE_DIR)),
    )

    start_time = time.time()
    run_timestamp = datetime.now(timezone.utc).isoformat()

    if mode == "book":
        validated, errors, info = run_book_mode(config, fetcher, reporter)
        records_filename, records_path = "books.json", reporter.save_books(validated)
    else:
        validated, errors, info = run_generic_mode(config, fetcher, reporter)
        records_filename, records_path = "pages.json", reporter.save_pages(validated)

    duration = round(time.time() - start_time, 3)
    pages_touched = fetcher.cache_hits + fetcher.network_fetches

    metrics = RunMetrics(
        run_timestamp=run_timestamp,
        run_name=run_dir.name,
        mode=mode,
        target_url=config.BASE_URL,
        duration_seconds=duration,
        pages_crawled=pages_touched,
        links_discovered=len(validated) + len(errors) + info["broken_pages"],
        records_validated=len(validated),
        failed_records=len(errors),
        cache_hits=fetcher.cache_hits,
        network_fetches=fetcher.network_fetches,
        broken_pages=info["broken_pages"],
    )
    report_path = reporter.save_report(metrics)
    errors_path = reporter.save_errors(errors)

    ui.stage("Done")
    ui.summary_table([
        ("Target", config.BASE_URL),
        ("Mode", mode),
        ("Requests", f"{fetcher.network_fetches} network / {fetcher.cache_hits} cache"),
        ("Records saved", len(validated)),
        ("Failed", len(errors)),
        ("Duration", f"{duration}s"),
    ])
    ui.files_table([
        (records_filename, str(records_path)),
        ("errors.json", str(errors_path)),
        ("run-report.json", str(report_path)),
    ])
    ui.errors_table(errors)

    return 0


def main() -> int:
    parser = cli.build_parser()
    args = parser.parse_args()
    try:
        return run(args)
    except KeyboardInterrupt:
        ui.warn("Interrupted — exiting")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
