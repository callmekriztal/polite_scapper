import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from polite_scraper import ui
from polite_scraper.config import Config


@dataclass
class RunMetrics:
    run_timestamp: str
    run_name: str
    mode: str
    target_url: str
    duration_seconds: float
    pages_crawled: int
    links_discovered: int
    records_validated: int
    failed_records: int
    cache_hits: int
    network_fetches: int
    broken_pages: int


class Reporter:
    """Handles writing validated dataset, error log, and execution report."""

    def __init__(self, config: Config):
        self.config = config

    def _write_json(self, target_path: Path, data: Any) -> Path | None:
        """Central JSON writer. A failed write (blocked path, disk full,
        permissions, ...) is reported to the user and returns None instead of
        crashing the run — all scraping work has already been done here."""
        try:
            self.config.ensure_directories()
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as ex:
            ui.error(f"Could not write {target_path}: {ex}")
            return None
        return target_path

    def save_records(self, records: list[Any], filename: str) -> Path | None:
        target_path = self.config.OUTPUT_DIR / filename

        # Serialize Pydantic objects to dicts
        data = [r.model_dump(mode="json") for r in records]

        if self._write_json(target_path, data) is None:
            return None

        ui.debug(f"STORED {len(records)} records -> {target_path}")
        return target_path

    def save_books(self, records: list[Any]) -> Path | None:
        return self.save_records(records, "books.json")

    def save_pages(self, records: list[Any]) -> Path | None:
        return self.save_records(records, "pages.json")

    def save_errors(self, errors: list[dict[str, Any]]) -> Path | None:
        target_path = self.config.OUTPUT_DIR / "errors.json"

        if self._write_json(target_path, errors) is None:
            return None

        if errors:
            ui.debug(f"STORED {len(errors)} error records -> {target_path}")
        return target_path

    def save_report(self, metrics: RunMetrics) -> Path | None:
        target_path = self.config.OUTPUT_DIR / "run-report.json"

        if self._write_json(target_path, asdict(metrics)) is None:
            return None

        ui.debug(f"STORED Run Report -> {target_path}")
        return target_path
