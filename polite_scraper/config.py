import os
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class Config:
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "PoliteScraper/1.0 (+https://github.com/callmekriztal/polite_scapper)"
    )
    TIMEOUT: int = int(os.getenv("TIMEOUT", "10"))
    MIN_DELAY_SECONDS: float = float(os.getenv("MIN_DELAY_SECONDS", "0.5"))
    
    # Paths (repo root is the package's parent directory)
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    CACHE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "cache")
    # Root for per-run output folders (e.g. data/runs/books-toscrape)
    OUTPUT_ROOT: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "runs")
    # The active run's output folder, resolved at runtime from the website name
    OUTPUT_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "runs")
    
    BASE_URL: str = "https://books.toscrape.com/"
    START_URL: str = "https://books.toscrape.com/catalogue/page-1.html"
    MAX_CATALOGUE_PAGES: int = 3

    # Generic-mode settings (set by the CLI)
    FORCE_REFRESH: bool = False
    MAX_LINKS_PER_PAGE: int = 8

    # Simulation hook for broken detail page testing
    BROKEN_TEST_URL: str | None = os.getenv("BROKEN_TEST_URL", None)

    def toscrape_start_url(self) -> str:
        """The Books to Scrape catalogue root, used when the user passes the site root."""
        return self.BASE_URL.rstrip("/") + "/catalogue/page-1.html"

    def ensure_directories(self) -> None:
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
