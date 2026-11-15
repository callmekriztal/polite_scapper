# Module: `reporter.py`

Source: `polite_scraper/reporter.py` (71 lines)

## A. Purpose

Persistence layer: writes the run's four JSON artifacts into `config.OUTPUT_DIR`. It is the *only* module that writes result files, and it never makes network calls or parses HTML.

## B. Imports

```python
import json                                   # line 1
from dataclasses import asdict, dataclass     # line 2 — RunMetrics serialization
from pathlib import Path                      # line 3 — return types
from typing import Any                        # line 4
from polite_scraper import ui                 # line 6 — debug logging
from polite_scraper.config import Config      # line 7
```

## C. Classes and functions

### `@dataclass class RunMetrics` (lines 10–23)

Twelve plain-typed fields:

| Field | Filled from (main.py) |
|---|---|
| `run_timestamp` | `datetime.now(timezone.utc).isoformat()` after mode resolution (165) |
| `run_name` | `run_dir.name` (179) |
| `mode` | resolved mode (180) |
| `target_url` | `config.BASE_URL` (181) |
| `duration_seconds` | wall clock of the pipeline stage (174, 182) |
| `pages_crawled` | `fetcher.cache_hits + fetcher.network_fetches` (175) |
| `links_discovered` | `len(validated) + len(errors) + broken_pages` (184) — *misnamed: counts records processed, not links discovered* |
| `records_validated` | `len(validated)` (185) |
| `failed_records` | `len(errors)` (186) |
| `cache_hits` / `network_fetches` | Fetcher counters (187–188) |
| `broken_pages` | mode runner info dict (189) |

Serialized with `dataclasses.asdict` (line 66) — a dataclass was chosen (instead of Pydantic) because it needs no validation, only shape.

### `class Reporter`

**`__init__(self, config)`** (29–30): stores config; `OUTPUT_DIR` is read *at save time*, not stored — so the runtime reassignment in `main.run` (line 147) is picked up naturally.

**`save_records(self, records: list[Any], filename: str) -> Path`** (32–43) — the general worker:

1. `ensure_directories()` (33) — defensive re-creation.
2. `target_path = self.config.OUTPUT_DIR / filename` (34).
3. `data = [r.model_dump(mode="json") for r in records]` (37) — Pydantic → JSON-safe dicts (`HttpUrl` → `str`).
4. `open(target_path, "w", encoding="utf-8")` + `json.dump(data, f, indent=2, ensure_ascii=False)` (39–40) — pretty-printed, non-ASCII preserved (`£` stays `£`).
5. `ui.debug(f"STORED ...")` (42) — visible only with `-v`.
6. Returns the `Path` — `main.run` collects it for `ui.files_table`.

**`save_books(records)` / `save_pages(records)`** (45–49): thin wrappers fixing `filename` to `books.json` / `pages.json`.

**`save_errors(self, errors) -> Path`** (51–60): writes `errors.json` — **always**, even when the list is empty (the file contains `[]`). This "empty file is a feature" behavior means downstream tooling never needs existence checks. The debug log only fires when errors exist (58–59).

**`save_report(self, metrics: RunMetrics) -> Path`** (62–71): `asdict(metrics)` → `run-report.json`.

No try/except anywhere: an unwritable path raises an unhandled `OSError` and crashes the run (verified — see [05_error_handling.md](../05_error_handling.md)).

## D. Execution

Constructed once in `main.run` (151). Called at `main.py` 169/172 (books/pages), 191 (report), 192 (errors). Order matters: records first, then report, then errors — matching the terminal summary's file list.

## E. Data flow

```text
main.run_book_mode ─► validated: list[BookRecord] ─► save_books ─► data/runs/<site>/books.json
main.run_generic_mode ─► validated: list[PageRecord] ─► save_pages ─► data/runs/<site>/pages.json
main.run ─► RunMetrics ─► save_report ─► run-report.json
main.run ─► errors: list[dict] ─► save_errors ─► errors.json
returned Paths ─► ui.files_table
```

## F. Design decisions

- **What it does:** one generic writer + three named wrappers; Pydantic serialization isolated here.
- **Interpretation:** `model_dump(mode="json")` centralized in `save_records` guarantees every record in every output file passes through the same serialization — no mode-specific code paths.
- **Interpretation:** writing `errors.json` even when empty makes runs self-describing; the absence of failures is itself recorded evidence.
- **Fact:** the reporter receives *validated Pydantic objects*, not dicts — it cannot write unvalidated data even by accident (the dicts in `errors.json` are the deliberate exception: they are the audit trail).

## G. Interview questions

1. **Why does `errors.json` exist even on perfect runs?** `save_errors` is unconditional (main.py 192); an empty `[]` file documents "no failures" — a self-describing dataset convention.
2. **Why `model_dump(mode="json")` and not `json.dumps(record.dict())`?** `mode="json"` applies Pydantic's JSON-mode serialization rules — crucially turning `HttpUrl` into `str`. Plain `.dict()` would leave `HttpUrl` objects that `json.dump` cannot serialize.
3. **Why is `RunMetrics` a dataclass while records are Pydantic?** Metrics need no validation (they're computed internally); `asdict` is stdlib. Using Pydantic here would add ceremony without value — a deliberate "right tool per job".
4. **Why does the reporter read `config.OUTPUT_DIR` at call time?** `main.run` assigns the per-run folder *after* constructing `Reporter` (147). Reading at save time means the reporter needs no knowledge of run-folder resolution.
5. **What is `ensure_ascii=False` for?** Keeps non-ASCII characters (`£`, accented titles) human-readable in the JSON instead of `\u00a3` escapes — pairs with the UTF-8 fix in `fetcher.py` 81.
6. **What happens if the disk is full?** `open`/`json.dump` raise `OSError` — unhandled; the run crashes after the scraping work was already done. Honest limitation: persistence errors are not caught (see 05_error_handling.md).
7. **Why return `Path` from every save method?** The orchestrator (`main.run` 203–207) passes them to `ui.files_table` — the return value is the terminal summary's input, not an error channel.

## H. Potential improvements

1. Wrap writes in try/except and surface a clean `ui.error` + non-zero exit instead of a traceback.
2. Atomic writes (write to `.tmp` then `os.replace`) would prevent half-written JSON on crash/kill — relevant because long runs + Ctrl-C is a real scenario (`main()` even catches KeyboardInterrupt).
3. `links_discovered` naming (main.py 184) — rename to `records_processed` or actually count discovery events.
4. Add file sizes to the report (cheap, useful for large runs).
5. Consider streaming writes (`json.dump` per record or NDJSON) for very large datasets — currently everything is materialized in memory first.
