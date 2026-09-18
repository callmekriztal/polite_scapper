import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from src.config import Config
from src.models import BookRecord

@dataclass
class RunMetrics:
    run_timestamp: str
    duration_seconds: float
    catalogue_pages: int
    discovered_urls: int
    unique_urls: int
    detail_pages: int
    successful_records: int
    failed_records: int
    cache_hits: int
    network_fetches: int
    broken_pages: int
    output_record_count: int

class Reporter:
    """Handles writing validated dataset, error log, and execution report."""

    def __init__(self, config: Config):
        self.config = config

    def save_books(self, records: list[BookRecord]) -> Path:
        self.config.ensure_directories()
        target_path = self.config.OUTPUT_DIR / "books.json"
        
        # Serialize Pydantic objects to dicts
        data = [r.model_dump(mode="json") for r in records]
        
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        print(f"STORED     {len(records)} records -> {target_path}")
        return target_path

    def save_errors(self, errors: list[dict[str, Any]]) -> Path:
        self.config.ensure_directories()
        target_path = self.config.OUTPUT_DIR / "errors.json"
        
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)
            
        if errors:
            print(f"STORED     {len(errors)} error records -> {target_path}")
        return target_path

    def save_report(self, metrics: RunMetrics) -> Path:
        self.config.ensure_directories()
        target_path = self.config.OUTPUT_DIR / "run-report.json"
        
        report_data = asdict(metrics)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
            
        print(f"STORED     Run Report -> {target_path}")
        return target_path
