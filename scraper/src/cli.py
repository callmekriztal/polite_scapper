"""Command-line interface for The Polite Scraper."""

import argparse
import os
from pathlib import Path

from src.config import Config

USAGE_EXAMPLES = """\
[bold]Examples:[/]
  python scraper/src/main.py https://books.toscrape.com
  python scraper/src/main.py https://en.wikipedia.org --mode generic --pages 10
  python scraper/src/main.py https://books.toscrape.com --mode book --pages 5 --force
  python scraper/src/main.py https://example.com -v          # verbose logs
"""


class Parser(argparse.ArgumentParser):
    def error(self, message: str):  # pragma: no cover - argparse hook
        from src import ui

        ui.error(f"{message}\n")
        ui.console.print(USAGE_EXAMPLES)
        raise SystemExit(2)


def build_parser() -> Parser:
    parser = Parser(
        prog="polite-scraper",
        description="A polite, rate-limited web scraper with caching and validation.",
        epilog=USAGE_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Website to scrape (e.g. https://books.toscrape.com)",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "book", "generic"],
        default="auto",
        help=(
            "Scraper mode: 'book' uses the catalogue/product-page extractor, "
            "'generic' extracts page metadata from any site, "
            "'auto' detects book catalogues and falls back to generic (default: auto)"
        ),
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="Maximum number of pages to crawl (default: 3)",
    )
    parser.add_argument(
        "--max-links",
        type=int,
        default=8,
        help="Generic mode only: max new same-domain links followed per page (default: 8)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Minimum delay in seconds between network requests (default: 0.5)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Network request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the local HTML cache and re-fetch everything",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed per-request logs and raw record checkpoints",
    )
    return parser


def build_config(args: argparse.Namespace) -> Config:
    """Map parsed CLI arguments onto a Config instance."""
    config = Config()

    if args.url:
        url = args.url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        config.BASE_URL = url if url.endswith("/") else f"{url}/"

    if args.delay is not None:
        config.MIN_DELAY_SECONDS = args.delay
    if args.timeout is not None:
        config.TIMEOUT = args.timeout
    config.MAX_CATALOGUE_PAGES = max(1, args.pages)
    config.FORCE_REFRESH = args.force
    config.MAX_LINKS_PER_PAGE = max(1, args.max_links)

    # Environment variables still work, but CLI flags win.
    env_ua = os.getenv("USER_AGENT")
    if env_ua:
        config.USER_AGENT = env_ua

    return config


def ensure_url_provided(args: argparse.Namespace) -> bool:
    from src import ui

    if args.url:
        return True
    ui.console.print(
        "[bold red]✗[/] No website given.\n"
        "  [dim]Usage:[/] polite-scraper [bold]<url>[/] [dim][options][/] \n"
    )
    ui.console.print(USAGE_EXAMPLES)
    return False
