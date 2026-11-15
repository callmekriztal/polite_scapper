# Module: `fetcher.py`

Source: `polite_scraper/fetcher.py` (94 lines)

## A. Purpose

The **only** module that talks to the network. It owns: the `requests.Session`, politeness (rate limiting), the disk cache, HTTP status policy (only 200 passes), and robots.txt retrieval. Everything else in the package asks *this* object for HTML.

## B. Imports

```python
import time                                       # line 1 — sleep for rate limiting
from urllib.robotparser import RobotFileParser    # line 2 — robots.txt rules (stdlib)
import requests                                   # line 4 — HTTP
from polite_scraper import ui                     # line 6 — verbose logging
from polite_scraper.config import Config          # line 7
from polite_scraper.utils import url_to_cache_filename  # line 8 — URL → cache filename
```

## C. Class: `Fetcher`

### `__init__(self, config)` (lines 14–22)

- Creates one `requests.Session()` and pins the `User-Agent` header (17–19). One session = connection reuse (HTTP keep-alive) across the entire run.
- State: `cache_hits = 0`, `network_fetches = 0`, `last_request_time = 0.0` — these counters are *the run's telemetry* and are later read by `main.run` for `RunMetrics` (main.py 187–188).

### `fetch(self, url: str, force_refresh: bool = False) -> tuple[str, bool]` (lines 24–48)

Returns `(html_content, was_cached)`; raises `requests.HTTPError` on any status != 200 (via `_network_get`).

Flow:

1. `force_refresh = force_refresh or self.config.FORCE_REFRESH` (30) — per-call override OR global `--force`.
2. `ensure_directories()` (31) — cache dir exists before any read/write.
3. `cache_filename = url_to_cache_filename(url)` (32) — deterministic mapping in `utils.py` 19–36: `catalogue/page-N.html` → `catalogue-page-N.html`; toscrape root/index → `catalogue-page-1.html`; `/catalogue/<slug>/index.html` → `detail-<slug[:30]>-<md5[:8]>.html`; anything else (i.e. all generic-mode URLs) → `detail-<md5>.html`.
4. **Cache read** (36–44): if file exists and not forcing, read it, bump `cache_hits`, `ui.debug` the hit, return `(text, True)`. A *cache read error* (corrupt file, permission) is swallowed and falls through to the network — resilience over purity.
5. **Network path** (46–47): `_network_get(url)` → then `cache_path.write_text(html, encoding="utf-8")` unconditionally — fresh HTML is always cached.

### `fetch_robots_txt(self, base_url: str) -> RobotFileParser | None` (lines 50–67)

- Builds `<base>/robots.txt`, `session.get(...)` inside `try/except RequestException` → `None` on network failure.
- Non-200 (e.g. the 404 that books.toscrape.com returns) → `None` → "no rules".
- Parses lines into a stdlib `RobotFileParser`.

**Verified gaps (deliberate to note in an interview):**
- This method uses `self.session.get` **directly**: it does not respect `MIN_DELAY_SECONDS`, does not go through `_network_get`, is not cached, and does not increment `network_fetches`.
- It treats 5xx (server-side robots.txt failure) the same as 404 ("no rules"). RFC 9309 suggests treating unreachable/temporarily-failing robots.txt cautiously; the pragmatic "no rules" choice is a documented trade-off, not an oversight to hide.

### `_network_get(self, url: str) -> str` (lines 69–94)

1. **Rate limiting** (70–75): `elapsed = now - last_request_time`; if `elapsed < MIN_DELAY_SECONDS`, `time.sleep(diff)`. This is a *global* limiter because every fetch shares this instance's `last_request_time`. It is a "minimum interval between requests" limiter, not a fixed sleep before each request — back-to-back cache-miss fetches each pay the gap only.
2. `ui.debug("FETCH ...")` → `self.last_request_time = time.time()` → `session.get(url, timeout=TIMEOUT)`.
3. `response.encoding = "utf-8"` (81) — forces UTF-8 decoding of `response.text`; `requests` otherwise trusts headers and may default to ISO-8859-1 when charset is missing, corrupting `£` into `Â£`. This one line is the fix for a real historical bug (documented in `docs/AI-VS-ME.md`).
4. **Status policy** (84–89): any status != 200 → `requests.HTTPError(f"HTTP fetch failed for {url} with status code {response.status_code}", response=response)`. **No retries exist anywhere in the project.**
5. Success: bump `network_fetches`, `ui.debug("FETCH OK ...")`, return `response.text`.

## D. Execution

Constructed once in `main.run` (main.py 150). Its `fetch` is called from: `main.resolve_mode_and_start` (probe, main.py 43), `CatalogueCrawler.discover_books` (crawler.py 26), `BookExtractor.extract_book` (extractor.py 30), `GenericSiteScraper.scrape` (generic.py 122). `fetch_robots_txt` is called only by `GenericSiteScraper.check_robots` (generic.py 94).

## E. Data flow

```text
                ┌──────────────────────────────────────────────┐
URL (str) ────► │ fetch(url)                                   │
                │   ├─ cache file exists? ──► (html, True)     │
                │   └─ else _network_get(url)                  │
                │        ├─ sleep (politeness)                 │
                │        ├─ session.get ──► 200? ──► html      │
                │        └─ else ──► HTTPError                 │
                │       cache_path.write_text(html)            │
                └──────────────┬───────────────────────────────┘
                               ▼
              (html, was_cached) → caller (crawler/extractor/generic/main)
```

Counters `cache_hits` / `network_fetches` flow out through `main.run` into `RunMetrics`.

## F. Design decisions

- **What it does:** cache-first, single-session, 200-only, no retries.
- **Interpretation:** the assignment this project was built for ("Stage 1: HTTP fetcher with local HTML caching and politeness delay" — see `docs/scraper.md`) mandated exactly these three behaviors; the class is a faithful, minimal implementation of that contract.
- **Interpretation:** caching raw HTML (not parsed results) means extractor logic can be rewritten and re-run instantly against the same corpus.
- **Fact:** the rate limiter uses wall-clock subtraction rather than a token bucket — simple, single-threaded appropriate.

## G. Interview questions

1. **Why one `Session` instead of `requests.get` per call?** Connection reuse (keep-alive) plus one place to pin the `User-Agent`; also the shared `last_request_time` makes the politeness delay global across all modules.
2. **How does the rate limiter work exactly?** Before each live request it measures elapsed time since the previous live request and sleeps the remainder of `MIN_DELAY_SECONDS` (fetcher.py 70–75). Cache reads bypass it entirely, so warm runs sleep zero times.
3. **Why force `response.encoding = "utf-8"`?** Without an explicit charset, `requests` falls back to ISO-8859-1 for `text/*` content; `£` would decode as `Â£`. Setting `.encoding` before touching `.text` re-decodes correctly.
4. **Why raise on non-200 instead of retrying or returning None?** The project's stated policy is strict: only 200 is a successful fetch (line 84). Exceptions are then handled *per item* by callers (main.py 98 / generic.py 123), which keeps the fetcher pure and the resilience policy in the orchestrator.
5. **What happens on a cache read error?** The `except` at line 43 logs via `ui.debug` and falls through to a network fetch — the cache is best-effort, never a hard dependency.
6. **Is the cache name collision-safe?** Yes for arbitrary URLs (full MD5 hash); toscrape catalogue pages get readable names (`catalogue-page-N`); detail pages get `slug[:30] + md5[:8]` (utils.py 29–33). Two different toscrape pages with identical first-30-slug-chars are still distinguished by the hash.
7. **Does the robots.txt fetch respect politeness?** No — verified gap: `fetch_robots_txt` calls `session.get` directly (line 57), skipping the delay and metrics. It is a single request per run, so impact is minimal, but it is a real inconsistency.
8. **Why cache on every successful fetch even when `--force` was used?** `--force` means "re-fetch", not "don't cache" (line 47 runs after `_network_get` regardless) — so forcing refresh refreshes the cache too.
9. **How would you add retries without breaking the design?** Add a bounded retry loop inside `_network_get` for idempotent GETs (5xx/timeouts only), keeping the 200-only policy and informing `RunMetrics` of attempt counts.

## H. Potential improvements

1. robots.txt should honor the rate limit and be counted in metrics (line 57).
2. `url_to_cache_filename`'s `detail-` prefix names generic-mode pages misleadingly (utils.py 35–36) — a `page-<md5>` prefix for non-toscrape URLs would be clearer.
3. No `Content-Type` check: a 200 response that is not HTML (e.g. a PDF) will be parsed by BeautifulSoup and likely yield an empty title — handled downstream as an error record, but a `text/html` check would be cheaper.
4. No timeout differentiation (connect vs read), no retry/backoff — acceptable for the sandbox targets, a real gap for production scraping.
5. `last_request_time` starts at 0.0, so the first request never sleeps — correct as-is, but worth a comment because `time.time() - 0.0` is a large number that just passes the check.
