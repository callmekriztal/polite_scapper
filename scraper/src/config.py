import os
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class Config:
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "FlyRankInternshipA9/1.0 (+https://github.com/YOUR_USERNAME/YOUR_REPO)"
    )
    TIMEOUT: int = int(os.getenv("TIMEOUT", "10"))
    MIN_DELAY_SECONDS: float = float(os.getenv("MIN_DELAY_SECONDS", "0.5"))
    
    # Paths relative to scraper root or project root
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    CACHE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "cache")
    OUTPUT_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "output")
    
    BASE_URL: str = "https://books.toscrape.com/"
    START_URL: str = "https://books.toscrape.com/catalogue/page-1.html"
    MAX_CATALOGUE_PAGES: int = 3
    
    # Simulation hook for broken detail page testing
    BROKEN_TEST_URL: str | None = os.getenv("BROKEN_TEST_URL", None)

    def ensure_directories(self) -> None:
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
