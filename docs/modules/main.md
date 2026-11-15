# Module: `main.py`

Source: `polite_scraper/main.py` (224 lines)

## A. Purpose

The orchestrator: receives parsed arguments, wires all services together, picks the mode, drives the crawl/extract/validate pipelines, and produces the run report + terminal summary. It contains **no HTML parsing and no HTTP code** — it composes modules that do.

## B. Imports

```python
import sys, time                                    # lines 1, 2 — path hack, wall clock
from datetime import datetime, timezone             # line 3 — run_timestamp
from pathlib import Path                            # line 4 — path hack
from urllib.parse import urlparse                   # line 5 — toscrape-root detection
import requests                                     # line 7 — catch RequestException in the probe
from bs4 import BeautifulSoup                       # line 8 — auto-detect probe parsing

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # line 11 — script-run support

from polite_scraper import cli, ui                  # line 13
from polite_scraper.config import Config            # line 14
from polite_scraper.crawler import CatalogueCrawler # line 15
from polite_scraper.extractor import BookExtractor  # line 16
from polite_scraper.fetcher import Fetcher          # line 17
from polite_scraper.generic import GenericSiteScraper  # line 18
from polite_scraper.reporter import Reporter, RunMetrics  # line 19
from polite_scraper.validator import RecordValidator   # line 20
```

Line 11 is what allows `python polite_scraper/main.py` (direct script) in addition to `python -m polite_scraper`: it puts the *repo root* on `sys.path` so `import polite_scraper.*` resolves. When run via `python -m`, it is redundant but harmless.

## C. Functions

### `resolve_mode_and_start(config, fetcher, requested_mode) -> tuple[str, str]` (23–50)

Detailed in [02_complete_data_flow.md](../02_complete_data_flow.md) Stage 5. Key facts:

- `is_toscrape_root` (33) is a **substring** check (`"books.toscrape.com" in given_url`) plus empty path — so `https://notbooks.toscrape.com/` would match it. Harmless but imprecise; a `netloc ==` comparison would be exact.
- `auto` probe (42–50): fetch `book_start` → `BeautifulSoup` → `soup.select("article.product_pod")` truthiness decides the mode. Unreachable target → `ui.error` + `SystemExit(1)` (44–46) — the only network failure converted to a clean exit.

### `run_book_mode(config, fetcher, reporter) -> tuple[list, list, dict]` (53–110)

- Constructs `CatalogueCrawler` and `BookExtractor` locally (55–56) — they are cheap, stateless-configuration objects; only `Fetcher`/`Reporter` are shared across modes.
- Discovery under an indeterminate spinner (58–61).
- **`reporter` parameter is unused in this function** — verified; persistence happens in `run()`. Same for `run_generic_mode` (113). Code smell: parameter exists for historical reasons.
- Extraction loop (77–107): per-URL try/except `Exception` (98) → error record + continue; `finally: progress.advance(task)` (106–107) keeps the progress bar honest regardless of outcome.
- Returns `(validated_records, error_records, {"broken_pages": n})` — an *info dict*, not a bool, so callers can extend without changing the tuple shape.

### `run_generic_mode(config, fetcher, reporter) -> tuple[list, list, dict]` (113–137)

- `scraper.check_robots(config.START_URL)` (117): `False` → `ui.error` + `SystemExit(1)` (118–119) — the robots-abort path.
- `scraper.scrape()` (124) → validation loop (130–135) with `RecordValidator.validate_page`.
- Returns `{"broken_pages": 0}` — generic-mode fetch failures are already inside `error_records`, so the counter stays zero here by construction.

### `run(args) -> int` (140–210)

The run lifecycle, in order:

1. `ui.set_verbose(args.verbose)` (141).
2. `cli.ensure_url_provided(args)` (142–143) — `False` → return 2.
3. `cli.build_config(args)` (145) → `config`.
4. `cli.resolve_output_dir(config, args.name)` (146) → `run_dir`; **`config.OUTPUT_DIR = run_dir`** (147) — the single assignment that routes all persistence.
5. `config.ensure_directories()` (148) — creates cache + run folder *before* any fetch (so cache writes succeed).
6. `Fetcher(config)` / `Reporter(config)` (150–151) — one of each per run.
7. `mode, config.START_URL = resolve_mode_and_start(...)` (153) — note the tuple-unpack assignment back into config: the mode runners and crawlers read `config.START_URL`, never the local variable.
8. `ui.banner(...)` (155–162).
9. Timers: `start_time` *after* mode resolution (164) — duration measures the pipeline, not the probe.
10. Mode dispatch (167–172): book → `save_books` → `("books.json", path)`; generic → `save_pages` → `("pages.json", path)`.
11. `RunMetrics` assembly (177–190) — including the two naming caveats: `pages_crawled = cache_hits + network_fetches` (includes robots.txt? No — robots fetch bypasses the counters) and `links_discovered = validated + failed + broken` (counts records).
12. `save_report` → `save_errors` (191–192) — `errors.json` always written.
13. Terminal summary (194–208): `stage("Done")`, `summary_table`, `files_table`, `errors_table`.
14. `return 0` (210) — **even when errors exist**; failures are quarantined, not fatal.

### `main() -> int` (213–220)

```python
parser = cli.build_parser()
args = parser.parse_args()
try:
    return run(args)
except KeyboardInterrupt:
    ui.warn("Interrupted — exiting")
    return 130
```

The only exception contract: KeyboardInterrupt → exit 130. Everything else (including `SystemExit` from argparse, mode resolution, and robots abort) propagates by design.

### `if __name__ == "__main__": raise SystemExit(main())` (223–224)

Direct-script entry (`python polite_scraper/main.py`). The `python -m` path enters through `__main__.py` instead, which imports `main` from here.

## D. Execution & E. Data flow

Full walk-through in [02_complete_data_flow.md](../02_complete_data_flow.md) and entry-point semantics in [04_execution_and_entry_points.md](../04_execution_and_entry_points.md).

```text
Namespace ─► run() ─► Config+run_dir ─► Fetcher/Reporter
                    ─► mode ─► run_book_mode / run_generic_mode
                                      │ (validated, errors, info)
                                      ▼
                        RunMetrics ─► reporter (3 files)
                                      ▼
                        ui panels ─► exit code
```

## F. Design decisions

- **What it does:** dependency composition + policy (mode, error accounting, exit codes) lives here; mechanics live in the modules.
- **Interpretation:** per-item try/except in the extraction loop (98) implements the assignment's "broken page resilience" requirement — isolation at the *orchestrator*, not inside `extract_book`, keeps the extractor honest (it raises) while the run survives.
- **Interpretation:** mode runners return `(list, list, dict)` instead of writing files themselves, so persistence ordering (records → report → errors) stays in one place.

## G. Interview questions

1. **What is the single most important line in `run()`?** `config.OUTPUT_DIR = run_dir` (147) — every downstream writer reads it; it's how a "run" gets its folder.
2. **Where can this program exit non-zero, exactly?** `Parser.error` → 2 (bad argv); `ensure_url_provided` → 2 (no URL); `resolve_mode_and_start` probe failure → 1; robots denial → 1; KeyboardInterrupt → 130; success → 0 (with or without quarantined errors). Also: an unhandled exception in book-mode discovery → traceback (exit 1 from the interpreter).
3. **Why does the progress bar advance in a `finally` block?** So failed pages still tick the bar (106–107) — otherwise the bar would lie about position after any exception.
4. **Why is `reporter` passed into the mode runners if unused?** Verified dead parameter (53, 113). Honest answer: leftover from an earlier design where runners persisted their own output; now persistence is centralized in `run()`.
5. **What state does a run share between modes?** Only what `run()` creates: `config` (mutable `OUTPUT_DIR`/`START_URL`), `fetcher` (session + counters), `reporter` (paths). Mode runners create their own crawler/extractor/scraper.
6. **Why measure duration after mode resolution?** The probe fetch is part of mode *detection*, not the scrape; keeping it out of `duration_seconds` makes warm-cache runs report ~0.8s instead of a misleading total.
7. **What happens if the user passes a toscrape URL directly to a book detail page?** `resolve_mode_and_start`: path is non-empty → `is_toscrape_root` False → `book_start = given_url`; auto-probe fetches the detail page, finds no `article.product_pod` → generic mode scrapes that single page. Sensible degradation worth demonstrating.

## H. Potential improvements

1. Wrap `discovery = crawler.discover_books()` (61) in try/except → error record + clean exit instead of a traceback (the biggest verified gap in the codebase).
2. Remove the unused `reporter` parameters (53, 113).
3. Exit code policy: consider non-zero (or a distinct code) when `errors` exist, for CI consumers — currently `0` always on completed runs.
4. `run()` is ~70 lines doing config + orchestration + reporting; a small `RunContext` object would slim it.
5. The `sys.path` insert (11) is unnecessary when installed/`-m`-run; guard it with `__name__ == "__main__"`-style check or delete after confirming only script-runs need it.
