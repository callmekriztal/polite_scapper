"""Command-line interface for The Polite Scraper."""

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from polite_scraper import __version__
from polite_scraper.config import Config

USAGE_EXAMPLES = """\
[bold]Examples:[/]
  python -m polite_scraper https://books.toscrape.com
  python -m polite_scraper https://en.wikipedia.org --mode generic --pages 10
  python -m polite_scraper https://books.toscrape.com --mode book --pages 5 --force
  python -m polite_scraper https://example.com -v          # verbose logs
"""


class Parser(argparse.ArgumentParser):
    def error(self, message: str):  # pragma: no cover - argparse hook
        from polite_scraper import ui

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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Custom name for this run's output folder (default: derived from the website name)",
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


def derive_run_name(base_url: str) -> str:
    """Derive a filesystem-safe run folder name from the website, e.g.
    'https://www.books.toscrape.com/' -> 'books-toscrape'."""
    host = urlparse(base_url).netloc.lower()
    host = re.sub(r"^www\.", "", host)
    name = re.sub(r"[^a-z0-9-]+", "-", host).strip("-")
    return name or "run"


def resolve_output_dir(config: Config, explicit_name: str | None) -> Path:
    """
    Resolve the per-run output folder under config.OUTPUT_ROOT.

    The default name comes from the website (e.g. 'books-toscrape'). If the
    folder already exists, the user is asked to pick a new name or accept an
    auto-suffix ('books-toscrape-1', 'books-toscrape-2', ...). In
    non-interactive sessions the auto-suffix is applied silently, so runs
    never overwrite a previous project's output.
    """
    base_name = (explicit_name or derive_run_name(config.BASE_URL)).strip()
    base_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", base_name).strip("-") or "run"

    candidate = config.OUTPUT_ROOT / base_name
    if not candidate.exists():
        return candidate

    # Collision: find the next free suffix
    suffix = 1
    while (config.OUTPUT_ROOT / f"{base_name}-{suffix}").exists():
        suffix += 1
    auto_name = f"{base_name}-{suffix}"

    if not sys.stdin.isatty():
        from polite_scraper import ui

        ui.info(f"Output folder '{base_name}' already exists — using '{auto_name}'")
        return config.OUTPUT_ROOT / auto_name

    # Interactive: let the user rename or accept the auto-suffix
    from polite_scraper import ui

    ui.warn(f"Output folder '{base_name}' already exists.")
    while True:
        answer = input(
            f"  New folder name [{auto_name}]: "
        ).strip()
        answer = re.sub(r"[^a-zA-Z0-9_-]+", "-", answer).strip("-")
        if not answer:
            return config.OUTPUT_ROOT / auto_name
        if not (config.OUTPUT_ROOT / answer).exists():
            return config.OUTPUT_ROOT / answer
        ui.warn(f"'{answer}' also exists — pick another name")


def ensure_url_provided(args: argparse.Namespace) -> bool:
    from polite_scraper import ui

    if args.url:
        return True
    ui.console.print(
        "[bold red]✗[/] No website given.\n"
        "  [dim]Usage:[/] polite-scraper [bold]<url>[/] [dim][options][/] \n"
    )
    ui.console.print(USAGE_EXAMPLES)
    return False
