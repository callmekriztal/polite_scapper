# Module: `config.py`

Source: `polite_scraper/config.py` (40 lines)

## A. Purpose

Single holder of every setting: identity (User-Agent), network behavior (timeout, delay), crawl limits, paths (cache, run outputs), and the target-site special cases. Nothing else in the package reads environment variables for these settings.

## B. Imports

```python
import os                                   # line 1 — env defaults
from pathlib import Path                    # line 2
from dataclasses import dataclass, field    # line 3
```

## C. Class: `Config` (dataclass, lines 5–40)

### Fields

| Field | Default | Source | Used by |
|---|---|---|---|
| `USER_AGENT: str` | `PoliteScraper/1.0 (+https://github.com/callmekriztal/polite_scapper)` | `os.getenv("USER_AGENT", ...)` at **class definition time** | `Fetcher` session header (fetcher.py 17–19); robots.txt identity (generic.py 98, 152) |
| `TIMEOUT: int` | `10` | env `TIMEOUT` | every `session.get(..., timeout=...)` (fetcher.py 57, 80) |
| `MIN_DELAY_SECONDS: float` | `0.5` | env `MIN_DELAY_SECONDS` | rate limiter (fetcher.py 70–75) |
| `CACHE_DIR: Path` | `Path.cwd()/data/cache` | default_factory | fetcher.py 33 |
| `OUTPUT_ROOT: Path` | `Path.cwd()/data/runs` | default_factory | cli.resolve_output_dir 150–156 |
| `OUTPUT_DIR: Path` | `Path.cwd()/data/runs` (replaced at runtime) | default_factory | reporter.py 34/53/64 |
| `BASE_URL: str` | `https://books.toscrape.com/` | CLI (cli.py 106–110) | mode resolution, naming |
| `START_URL: str` | toscrape `catalogue/page-1.html` | mode resolution (main.py 153) | crawler 20, generic 107 |
| `MAX_CATALOGUE_PAGES: int` | `3` | `--pages` | crawler 25, generic 108 |
| `FORCE_REFRESH: bool` | `False` | `--force` | fetcher.py 30 |
| `MAX_LINKS_PER_PAGE: int` | `8` | `--max-links` | generic.py 109 |
| `BROKEN_TEST_URL: str \| None` | env `BROKEN_TEST_URL` | — | extractor.py 26–27 test hook |

### Methods

- **`toscrape_start_url(self) -> str`** (34–36): `BASE_URL.rstrip("/") + "/catalogue/page-1.html"`. Used by `main.resolve_mode_and_start` when the user passed the toscrape root and book mode applies.
- **`ensure_directories(self) -> None`** (38–40): `mkdir(parents=True, exist_ok=True)` on `CACHE_DIR` and `OUTPUT_DIR`. Called from `main.run` (148), `Fetcher.fetch` (31), and all three `Reporter.save_*` methods — deliberately idempotent and cheap, so any module can call it defensively.

## D. Execution

`Config` is instantiated in `cli.build_config` (line 104) and directly in tests (`tests/test_scraper.py` 53, 144). Dataclass field defaults are evaluated **when the class body is defined** for plain values (`os.getenv` on lines 7–12, 32) but *per-instantiation* for `field(default_factory=...)` paths (lines 17–21). Practical consequence: setting `TIMEOUT` via env after the interpreter has imported the package has no effect; `CACHE_DIR` etc. reflect the *current working directory at instantiation time*.

## E. Data flow

```text
env vars ─► (import-time) ─► class defaults ─┐
cli.build_config ─► overrides ───────────────┤
                                             ▼
                                    Config instance
                          ├─► Fetcher (UA, TIMEOUT, MIN_DELAY, CACHE_DIR, FORCE_REFRESH)
                          ├─► CatalogueCrawler (START_URL, MAX_CATALOGUE_PAGES)
                          ├─► GenericSiteScraper (START_URL, MAX_PAGES, MAX_LINKS, UA)
                          ├─► Reporter (OUTPUT_DIR)
                          └─► main (OUTPUT_ROOT via cli, OUTPUT_DIR, paths for ui.banner)
```

## F. Design decisions

- **What it does:** a mutable dataclass, not frozen — the pipeline mutates `OUTPUT_DIR` (main.py 147) and `START_URL` (153) after construction.
- **Interpretation:** making `Config` a dataclass rather than constants gives tests a cheap seam — `tests/test_scraper.py` lines 53–55 and 144–146 override `CACHE_DIR`/`OUTPUT_DIR`/`OUTPUT_ROOT` per test without touching globals.
- **Interpretation:** cwd-relative data paths (comment on lines 14–16) exist because of packaging: an installed wheel must never write into `site-packages`. Working-directory-relative paths mean a scraper run's evidence belongs to the directory you run it in.
- **Fact:** `BROKEN_TEST_URL` is a *test hook*, not a feature: it only triggers when the URL string matches exactly (`extractor.py` 26) and exists so broken-page handling can be tested offline.

## G. Interview questions

1. **When do env defaults actually get read?** At class-definition (import) time for the scalar fields (`os.getenv` inside the class body, lines 7–12/32) — not per-instance. `Path.cwd()`-based paths, by contrast, are evaluated per instantiation via `default_factory`.
2. **Why is `OUTPUT_DIR` mutable while everything else is treated as read-only?** The per-run folder depends on the website and collision state, which are known only after parsing the URL; mutating one field is simpler than threading a `run_dir` parameter through every writer.
3. **Why does `ensure_directories` exist if `mkdir(parents=True)` is idempotent?** It centralizes the two directories every I/O module needs, so `Fetcher.fetch` and `Reporter.save_*` can be defensive without importing each other.
4. **What breaks if you run the tool from a different working directory?** Cache and outputs follow the cwd: `data/cache` in the new cwd is cold (first run re-fetches), and runs land in the new cwd's `data/runs`. That is deliberate post-packaging behavior — installed copies must not write inside site-packages.
5. **Why is the User-Agent sent as a header instead of a query/param?** Standard crawler etiquette/HTTP practice: `requests.Session.headers` applies it to every request made by the session, including robots.txt — and it is also the identity string checked against robots.txt rules via `can_fetch`.
6. **What is `BROKEN_TEST_URL` for?** A deterministic failure injector: `extract_book` raises `HTTPError` when a product URL equals it, letting `tests/test_scraper.py::test_broken_detail_page_simulation` verify per-page error resilience without real network failures.
7. **Is `START_URL` used by both modes?** Yes — the crawler reads `config.START_URL` (crawler.py 20) and the generic scraper reads it (generic.py 107). It is *rewritten* by `resolve_mode_and_start` in main (153) so both modes share one knob.

## H. Potential improvements

1. Env defaults baked at import time (lines 7–12) are surprising; move them into `build_config` or use `default_factory=lambda: os.getenv(...)` for consistency with the path fields.
2. `toscrape_start_url` hardcodes a site-specific path inside generic settings — a candidate for a per-site "profile" concept if more targets are supported.
3. No validation of `MIN_DELAY_SECONDS`/`TIMEOUT` bounds (`--delay 0` disables politeness silently; that is the user's choice, but a warning would be cheap).
4. `OUTPUT_ROOT` has no `ensure_directories` call of its own — only the child `OUTPUT_DIR` is created; harmless today, surprising if someone writes to `OUTPUT_ROOT` directly.
