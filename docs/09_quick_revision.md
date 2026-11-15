# 09 — Quick Revision (20–30 minutes)

Last pass before the interview. Every line is verified against the v1.0.1 source.

## 1. Project summary (memorize this paragraph)

Polite Scraper = CLI web scraper, published to PyPI as `polite-scraper` (v1.0.1, MIT). One required argument: the URL. Two modes: **book** (pagination crawler + product extractor for catalogue sites) and **generic** (BFS over same-domain links, page metadata), with **auto** detection (probe for `article.product_pod`). Politeness: custom User-Agent, ≥500 ms between live requests, disk cache (re-runs = zero network), robots.txt in generic mode. Data normalized (`utils`) and validated (Pydantic `BookRecord`/`PageRecord`); failures quarantined to `errors.json`. Per-run output folders `data/runs/<site>/` with collision-safe suffixes. Rich terminal UI, quiet by default, `-v` for detail.

## 2. Architecture in one diagram

```text
CLI arg ─► cli.py ─► Config ─┬─► main.run (orchestrator)
                             │     ├─► Fetcher (only HTTP: cache, rate limit, robots.txt)
                             │     ├─► book: CatalogueCrawler ─► BookExtractor ─┐
                             │     ├─► generic: GenericSiteScraper ─────────────┤
                             │     ├─► RecordValidator ─► BookRecord/PageRecord │
                             │     └─► Reporter ─► books/pages/errors/run-report.json
                             └─► ui.py (all console output)
```

14 modules: `__init__` (version), `__main__` (-m shim), `main` (orchestration), `cli` (args + run folders), `config` (settings), `fetcher` (network), `crawler`+`extractor` (book), `generic` (generic), `models` (Pydantic), `validator` (gate), `reporter` (files), `ui` (terminal), `utils` (pure helpers).

## 3. Execution flow (10 steps)

1. `python -m polite_scraper` → `__init__` (version) → `__main__.py` → `main()` (main.py 213).
2. `cli.build_parser().parse_args()` → `Namespace` (bad argv → custom error, exit 2).
3. `main.run(args)`: `ui.set_verbose`; `ensure_url_provided` (else exit 2).
4. `cli.build_config`: scheme added, trailing slash, clamps; env UA applied.
5. `cli.resolve_output_dir`: site name (`books-toscrape-com`), collision → `-1` suffix (TTY prompt or silent).
6. `config.OUTPUT_DIR = run_dir`; `ensure_directories()`; `Fetcher(config)`, `Reporter(config)` — **one of each per run**.
7. `resolve_mode_and_start`: toscrape-root → `catalogue/page-1.html`; auto → probe fetch + `product_pod` check (unreachable → exit 1). Writes `config.START_URL`.
8. Book: `discover_books` (fetch pages, `product_pod`/`h3 a` links, dedupe set, `li.next` walk, ≤ `--pages` cap) → 60 URLs → per-URL `extract_book` (selectors + normalize) → `validate_record` → accumulate. Generic: `check_robots` (abort exit 1) → BFS `scrape()` → `validate_page`.
9. `save_books`/`save_pages`, `save_report`, `save_errors` (always written).
10. Summary panels; **exit 0** even with errors. Other codes: 1 (probe fail/robots), 2 (argv), 130 (Ctrl-C).

## 4. Module responsibilities (one line each)

| Module | Responsibility | Key call |
|---|---|---|
| main.py | orchestration | `run()`, `resolve_mode_and_start()`, `run_book_mode()`, `run_generic_mode()` |
| cli.py | args → Config, run folders | `build_parser/build_config/resolve_output_dir/derive_run_name` |
| config.py | settings (env-at-import!), cwd-relative data paths | `Config`, `toscrape_start_url()`, `ensure_directories()` |
| fetcher.py | only network: cache-first, 200-only, rate limit | `fetch()`, `fetch_robots_txt()` |
| crawler.py | book discovery: pagination walk | `discover_books()` → `DiscoveryResult` |
| extractor.py | book parsing: 6 selectors + normalize | `extract_book()` |
| generic.py | BFS + page metadata | `check_robots()`, `scrape()`, `GenericExtractor.extract_page()` |
| models.py | contracts: `BookRecord` (9 fields), `PageRecord` (10) | `model_validate` / `model_dump(mode="json")` |
| validator.py | exceptions → error dicts | `validate_record/validate_page/_validate` |
| reporter.py | JSON persistence | `save_books/save_pages/save_errors/save_report` |
| ui.py | rich output, `_VERBOSE` global | `debug/info/success/error/warn`, `banner`, `make_progress`, `*_table`, `checkpoint` |
| utils.py | pure helpers | `make_absolute_url`, `url_to_cache_filename`, `normalize_price/rating/availability`, `clean_text` |

## 5. Most important functions (be able to whiteboard these)

- `Fetcher.fetch` (fetcher.py 24–48): cache → `_network_get` → write cache. Returns `(html, was_cached)`.
- `Fetcher._network_get` (69–94): sleep remainder of delay → GET → `encoding="utf-8"` → non-200 → `HTTPError`.
- `CatalogueCrawler.discover_books` (crawler.py 19–59): while-loop, dedupe set, `li.next`.
- `BookExtractor.extract_book` (extractor.py 20–92): BROKEN_TEST_URL hook → fetch → `div.product_main` required → 6 selectors → normalize → dict.
- `GenericSiteScraper.scrape` (generic.py 105–148): BFS, per-page try/except, enqueue filters.
- `RecordValidator._validate` (validator.py 18–47): try model_validate / except ValidationError → error dict.
- `cli.resolve_output_dir` (cli.py 137–179): suffix search, TTY check, rename loop.

## 6. Dependencies

`requests` (HTTP), `beautifulsoup4` (parsing, always `html.parser`), `pydantic` v2 (contracts), `rich` (UI). Packaging: `pyproject.toml`, console script `polite-scraper = polite_scraper.main:main`, dynamic version from `__init__.__version__`. Tests: pytest only — **no mock libraries; all 10 tests offline**.

## 7. Key technical concepts (one-liners)

- **Rate limiting:** interval-based (sleep the remainder); global via one Fetcher; cache reads bypass.
- **Cache:** URL → deterministic filename (regex branches + MD5); raw HTML cached, not parsed data.
- **BFS:** `collections.deque.popleft()`; FIFO ≈ importance-ordered; `list.pop(0)` would be O(n).
- **urljoin:** resolves relative → absolute per RFC 3986; dedupe happens post-join.
- **Pydantic extras:** unknown keys are *ignored* by default → `rating_int`/`availability_normalized` dropped (real defect).
- **HttpUrl:** validates absolute URL; serializes via `model_dump(mode="json")`.
- **Exception chaining:** `raise ... from e` in models.py timestamp validator.
- **Errors-as-data:** validator + per-item loops → `errors.json`; exceptions for infrastructure only.
- **`transient=True`:** rich progress bars erase themselves after completion.
- **UTF-8 fix:** `response.encoding = "utf-8"` before `.text` (else `£` → `Â£`).

## 8. Common errors & where they surface

| Error | Meaning | Source |
|---|---|---|
| `No website given.` + exit 2 | forgot the URL | cli.py 187 |
| `Could not reach <url>` + exit 1 | auto-probe failed | main.py 45 |
| `robots.txt disallows ...` + exit 1 | generic-mode politeness | main.py 119 |
| `HTTP fetch failed ... status code N` | non-200 (per-item in extraction/generic; **crash** in book discovery) | fetcher.py 86 |
| `Could not find product_main area` | site markup changed | extractor.py 36 |
| `Price text is empty` / `Could not parse numeric price` | bad price | utils.py 41/45 |
| `Output folder 'X' already exists` | collision → suffix/prompt | cli.py 169 |
| Traceback in discovery | **known unhandled path** | main.py 61 |

## 9. Thirty likely interview questions (concise answers)

1. **What does it do?** Crawls a URL politely, extracts structured records, writes validated JSON per run.
2. **Two modes?** Book (catalogue crawler+extractor), generic (BFS+metadata); auto-detects via `product_pod` probe.
3. **How is politeness implemented?** UA header, ≥500 ms interval limiter, disk cache, robots.txt (generic), page budgets, 200-only.
4. **Why one Fetcher?** One session (keep-alive) + one rate-limit clock + one status/cache policy — global politeness by construction.
5. **How does the cache work?** Deterministic URL→filename (MD5-based), read-first, write-after-fetch, `--force` bypasses reads only.
6. **Cache-hit re-run cost?** Zero network requests; verified `0 network / 64 cache` on warm run.
7. **Rate limiter details?** Sleep `MIN_DELAY - elapsed` before each live request; not thread-safe; robots fetch bypasses it (known gap).
8. **How does auto-detection work?** Probe fetch, `soup.select("article.product_pod")`, bool decides mode.
9. **How does book crawling stop?** No `li.next a`, or page cap reached.
10. **Duplicate URLs?** Book: absolute-URL set. Generic: fragment-stripped set at enqueue.
11. **How does generic mode choose links?** Same netloc + unseen + robots-allowed + frontier guard + page budget.
12. **Why BFS?** Budget-friendly, deterministic, near-importance ordering; deque for O(1) pops.
13. **How is the rating extracted?** CSS class word → `RATING_MAP` word→int, unknown → 0.
14. **Price normalization?** First numeric group via regex → float; empty/unparseable → ValueError → error record.
15. **Availability?** Parsed to `{in_stock, quantity, raw}`; count from `(N available)` regex.
16. **Validation failure handling?** ValidationError caught → `(None, error dict)` → `errors.json`; run continues.
17. **What's in errors.json?** URL, reason, per-field `validation_errors`, and the full raw record (audit trail).
18. **Why errors-as-data?** One bad page must not kill a run; orchestrator accumulates.
19. **What's NOT handled?** Book-discovery network failure (crash), reporter write failures, robots 5xx as no-rules, no retries.
20. **Where does the User-Agent matter twice?** HTTP header + robots.txt `can_fetch` identity.
21. **Why cache HTML not JSON?** Extraction logic can evolve; re-parse is free.
22. **Why dataclass + Pydantic both?** Shape-only for Config/Metrics; runtime validation for untrusted records.
23. **`model_dump(mode="json")`?** JSON-safe serialization (`HttpUrl` → str) for `json.dump`.
24. **Exit codes?** 0 success (errors quarantined), 1 probe/robots, 2 argv, 130 Ctrl-C.
25. **What is `BROKEN_TEST_URL`?** Env-var test hook raising HTTPError for one URL — deterministic offline failure injection.
26. **How are run folders named?** Host-sanitized (`books-toscrape-com`), collision → `-1` suffix or interactive rename.
27. **Python entry points?** `polite-scraper` (console script → main), `python -m` (`__main__.py`), direct script (sys.path hack).
28. **What libraries and why?** requests/bs4/pydantic/rich — no browser, no lxml, no click: stdlib-first.
29. **What would break on a JS site?** Server HTML only; JS content → error records; fix = Playwright (deliberately out of scope).
30. **Biggest honest defect?** Book-discovery network failures crash the run (no per-page isolation) — first fix I'd make.

## 10. Ten difficult follow-ups

1. **"Your limiter isn't thread-safe — does that matter?"** Today the pipeline is single-threaded, so no. If we add a thread pool, the sleep-check must become a lock/token-bucket per host.
2. **"robots.txt 5xx → proceed: defend that."** Pragmatism: a 404 (no file) and a 500 (broken server) are hard to distinguish in intent; RFC leans conservative. I'd split: 404 proceed, 5xx warn-and-proceed with a flag, never silently.
3. **"Why ignore `was_cached` from fetch?"** Fact: callers discard it (`crawler.py` 26, `extractor.py` 30). It's part of the API for tests/diagnostics; metrics come from the counters instead.
4. **"Why does `discovered_count` equal `len(book_urls)`?"** Dedupe happens during append, so the "discovered" count isn't tracked separately — an artifact of the assignment's reporting requirement.
5. **"Probe fetch doubles the first request?"** No — it goes through the cache; the crawler's first fetch is then a cache hit. Detection is effectively free.
6. **"Is the cache TOCTOU-safe?"** `is_file()` then `read_text` guarded by try/except (fetcher.py 37–44); a deleted-between file falls back to network. Fine.
7. **"Why validate fetched_at as string not datetime?"** Preserves the exact ISO string in JSON (offset included); parseability is checked in the validator (models.py 23–30).
8. **"What does `include_url=False` do?"** Omits Pydantic's docs URL from each error entry in `errors.json` — cleaner data.
9. **"SSRF risk?"** Real if hosted: book/auto modes fetch any user URL including internal hosts. Mitigation: private-IP blocking at the fetcher. As a local dev tool, accepted risk.
10. **"Why `html.parser` over lxml?"** Zero extra dependency, pure-Python, adequate for these page sizes; lxml is the performance upgrade path (one dep, 5–10× parsing).

## 11. Implementation details you must remember

- Version lives in `polite_scraper/__init__.py` (`1.0.1`); pyproject reads it via `attr` — one bump updates `--version` + PyPI.
- `Config` env defaults are read **at import time** (config.py 7–12); paths are cwd-relative via `default_factory` (17–21).
- `main.run` mutates `config.OUTPUT_DIR` (147) and `config.START_URL` (153) — all downstream reads go through config.
- Timers: `start_time` set *after* mode resolution (main.py 164) → duration excludes the probe.
- `errors.json` is **always written** (even `[]`); `pages.json`/`books.json` per mode.
- `ui._VERBOSE` set once in `run()` (141) before anything prints.
- Extraction loop: `try/except Exception/finally advance` (main.py 81–107) — bar ticks even on failure.
- Generic dedupe strips fragments *twice*: link build (59) and seed (115).
- `normalize_price("£-10")` → `10.0` (sign dropped) — negative prices only rejected by Pydantic, and only if the float is negative, which normalize prevents. Subtle; be careful if asked.
- Tests: 10, offline, no mocking lib; `CatalogueCrawler` imported in tests but never used (verified).
- First PyPI release flow: tag `v1.0.1` → GitHub Action (pytest → build → trusted publish via OIDC, workflow `publish.yml`, environment `pypi`).
