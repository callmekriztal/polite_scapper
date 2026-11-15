# 06 — Technical Interview Preparation

## Part A — 60-second project introduction

> "The Polite Scraper is a Python CLI web scraper I built and published to PyPI as `polite-scraper`. You give it a URL and it crawls that site politely — identifying itself with a custom User-Agent, rate-limiting live requests to at most one per half-second, caching every page on disk so re-runs make zero network requests, and consulting robots.txt before following links. It has two extraction pipelines: a book-catalogue mode that walks pagination and extracts price/availability/rating records, and a generic mode that BFS-crawls same-domain links and extracts page metadata. Everything is validated with Pydantic schemas — bad records are quarantined into errors.json instead of crashing the run — and each run writes into its own collision-safe output folder named after the website. Internally it's 14 small modules with a single network gateway, a single output writer, and a rich-based terminal UI, with 10 offline tests."

Practice until this flows without notes. Every claim in it is verified in the docs that follow.

## Part B — Architecture questions

**B1. Walk me through the architecture.**
Five layers: interface (`cli.py`, `ui.py`), orchestration (`main.py`), services (`config.py`, `fetcher.py`, `reporter.py`), domain (`crawler.py`, `extractor.py`, `generic.py`), contracts (`models.py`, `validator.py`, `utils.py`). One `Fetcher` and one `Reporter` are constructed per run and injected everywhere; all HTTP goes through the fetcher, all files through the reporter, all terminal output through `ui`. Diagram: [01_project_architecture.md](01_project_architecture.md).

**B2. Why so many small modules instead of one script?**
Testability (pure functions in `utils.py`/`validator.py` test offline), separation of failure domains (network errors live in `fetcher.py`, parsing errors in the extractors), and swappability: the generic extractor never touches HTTP code. The modules communicate through dicts at the data boundary and injected objects at the service boundary.

**B3. How do the modules communicate?**
Three mechanisms: dependency injection (`Fetcher`/`Reporter`/`Config` passed into constructors), plain dicts as intermediate records (extractors → validator), and a module-level UI singleton (`ui.console` + `_VERBOSE`). No global mutable state beyond the UI flag.

**B4. What is the contract between crawler and extractor?**
`CatalogueCrawler.discover_books()` returns a `DiscoveryResult` whose `book_urls` is a list of `{"product_url", "source_page"}` dicts. `BookExtractor.extract_book(product_url, source_page)` consumes exactly that pair. The extractor knows nothing about pagination; the crawler knows nothing about product markup.

## Part C — Implementation questions

**C1. How does the rate limiter work?** `Fetcher._network_get` (fetcher.py 70–75): before each live request, sleep the remainder of `MIN_DELAY_SECONDS` since the previous live request. Instance-level clock — global because one Fetcher serves all modules. Cache reads bypass it. The robots.txt fetch bypasses it too (a named gap).

**C2. How does the cache work?** `fetcher.fetch`: URL → deterministic filename via `url_to_cache_filename` (utils.py 19–36: toscrape catalogue names, slug+md5[:8] for details, full md5 otherwise). Hit → read file, `cache_hits += 1`. Miss → `_network_get` → write file. `--force` skips reads but still re-writes. Cache read errors are swallowed and fall back to network (fetcher.py 43).

**C3. How does auto mode detection work?** `main.resolve_mode_and_start` (23–50): probe-fetch the start URL, `soup.select("article.product_pod")` — present = book mode, absent = generic. The probe result is cached, so detection is free on re-runs.

**C4. How does generic crawling decide what to visit?** Filters in order: same `netloc` (generic.py 58), not in `seen` (fragment-stripped, 115/143), robots-allowed (`_robots_allows`, 145), frontier guard (`--max-links` growth, 141), global `--pages` budget (118). BFS order via `deque.popleft()`.

**C5. How does validation failure become an error record?** `RecordValidator._validate` (validator.py 18–47): `model_validate` → on `ValidationError`, return `(None, {product_url, reason, validation_errors: ve.errors(include_url=False), raw_record})`. The orchestrator accumulates these; `Reporter.save_errors` writes them all to `errors.json`.

**C6. What does `model_dump(mode="json")` do and why is it needed?** Serializes Pydantic models to JSON-safe types — `HttpUrl` becomes `str` (reporter.py 37). Without `mode="json"`, `json.dump` would choke on `HttpUrl` objects.

**C7. How is the star rating extracted?** It's a CSS *class*, not text: `p.star-rating` with `class="star-rating Three"`. `extractor.py` 53–59 iterates the class list and takes the first class that isn't `star-rating`; `normalize_rating` maps the word via `RATING_MAP`.

**C8. How are run folders named and collision-safe?** `derive_run_name` (cli.py 128–134): host → strip `www.` → sanitize → `books-toscrape-com` (TLD kept for ambiguity safety). `resolve_output_dir` (137–179): first free `-N` suffix on collision; interactive rename prompt on TTY, silent suffix otherwise.

## Part D — Python questions

**D1. Why dataclasses in some places and Pydantic in others?** `Config`/`RunMetrics` need shape only (stdlib `@dataclass`, `asdict`). Scraped records need runtime validation of untrusted data — Pydantic's `Field(ge=...)`, `HttpUrl`, `field_validator` (models.py). Right tool per job.

**D2. Explain `default_factory` in the dataclass.** Mutable/derived defaults can't be plain values; `field(default_factory=lambda: Path.cwd() / "data" / "cache")` (config.py 17) evaluates per instantiation — also the fix for the classic `def f(x=[])` bug. Same pattern for `headings: list[str] = Field(default_factory=list)` (models.py 39).

**D3. `str | None` vs `Optional[str]`?** Identical semantics; `X | None` is the 3.10+ PEP 604 syntax. Both appear (config.py 32 uses `|`, models.py uses `Optional`).

**D4. Where is exception chaining used and why?** `models.py` 29–30: `raise ValueError(...) from e` inside the ISO-timestamp validator — preserves the original parse error for the traceback. Also relevant: `validator.py` *catches* `ValidationError` rather than chaining, because errors become data.

**D5. Why `deque` and not a list for the BFS queue?** `list.pop(0)` is O(n) (shifts all elements); `deque.popleft()` is O(1). `collections.deque` is the canonical BFS queue.

**D6. What does `@staticmethod` buy here?** `RecordValidator` has no state — static methods make that explicit. Honest answer: free functions would be equally good; the class mirrors the original structure (`docs/AI-VS-ME.md`).

**D7. How does `if __name__ == "__main__"` work in this project?** Two instances: `__main__.py` line 3 (true under `python -m`) and `main.py` line 223 (true under direct script execution). Detail: [04_execution_and_entry_points.md](04_execution_and_entry_points.md).

## Part E — Web technology questions

**E1. Why only accept HTTP 200?** Strict policy from the assignment (fetcher.py 84–89): redirects would be followed silently by `requests` but a 3xx/4xx/5xx final status means the content isn't what we asked for. Failures propagate as `HTTPError` to per-item handlers.

**E2. Why set `response.encoding = "utf-8"`?** Without an explicit charset header, `requests` falls back to ISO-8859-1 for `text/*`; `£` decodes as `Â£`. Setting `.encoding` *before* reading `.text` forces correct decoding (fetcher.py 81). This fixed a real historical bug (documented in `docs/AI-VS-ME.md`).

**E3. How do you respect robots.txt?** Fetch `<origin>/robots.txt`, parse with stdlib `RobotFileParser`, check with `can_fetch(our_user_agent, url)` — for the seed (abort on denial) and every candidate link (filter). Missing file (404) = no rules = proceed. Gaps: 5xx treated as no-rules; robots fetch itself skips the rate limit (fetcher.py 57).

**E4. Crawling vs scraping — where's the line in this project?** `crawler.py`/`generic.py` crawl (URL discovery, dedupe, budget); `extractor.py`/`GenericExtractor` scrape (HTML → fields). They share no selectors or logic.

**E5. How do you avoid hammering a server?** Five mechanisms: identifying UA, ≥500 ms between live requests, disk cache (re-runs cost zero), page/link budgets, robots.txt compliance in generic mode.

**E6. What would break on a JavaScript-rendered site?** The scrapers use BeautifulSoup on server HTML; JS-rendered content (SPA) would appear empty → generic mode yields "no page title" error records; book mode yields `product_main` ValueErrors. Fix would be Playwright/Selenium — deliberately out of scope (documented in `docs/scraper.md` "No Browser Overhead").

## Part F — Design decision defenses

**F1. Why is `Fetcher` the only network module?** One session (keep-alive), one rate-limit clock, one status policy, one cache. If `crawler.py` did its own HTTP, politeness would need coordination across modules — injecting the fetcher makes the limit global by construction.

**F2. Why raw dicts between stages instead of Pydantic everywhere?** Extraction is a *total* transform (never raises) that shouldn't hardcode schema knowledge; the validator is the single gate. Also keeps `errors.json` able to carry the raw payload for failed records — impossible if extraction produced models.

**F3. Why cache HTML instead of extracted JSON?** Extractor logic improves over time; re-parsing cached HTML is free. Caching parsed data would freeze results at extraction-time bugs.

**F4. Why errors-as-data instead of exceptions across the pipeline?** The run must survive 60 pages where 3 are broken (assignment requirement). `RecordValidator` and the per-item loops convert failures into `errors.json` entries; exceptions are reserved for *infrastructure* problems (unreachable probe, robots denial).

**F5. Why per-run output folders?** Repeated scrapes are the normal workflow (cache warm-ups, different dates, different `--pages`). Overwriting destroys evidence; the website-derived name makes `data/runs/` a browseable experiment log.

**F6. Why `argparse` over click/typer?** Ten options don't justify a dependency; argparse is stdlib, and the custom `Parser.error` gives friendly output. Would switch at ~30 options or when subcommands appear.

## Part G — Real challenges (vs. hypothetical)

*Real, observed in this code:*
1. Encoding corruption (`£` → `Â£`) — fixed with explicit encoding (fetcher.py 81).
2. Cache-key collision bug in early versions (all detail pages matching catalogue-page-1) — fixed by regex disambiguation in `url_to_cache_filename` (documented in `docs/AI-VS-ME.md`).
3. Keeping the terminal clean while logging per-request — solved with the verbose-gated `ui.debug`.
4. Run overwrite problem — solved with collision-suffixed run folders.

*Hypothetical for this code (be honest):* JavaScript rendering, distributed crawling, incremental re-crawls, content deduplication — none exist here; say so plainly.

## Part H — Critical questions with model answers

**"Why did you design the project this way?"** — "Assignment-driven pipeline stages (fetch → crawl → extract → normalize → validate → report) that each became a module. The constraint that shaped everything: politeness. One shared Fetcher gives one rate-limit clock; the cache gives zero-cost re-runs."

**"What happens when a website is unavailable?"** — "Depends where. Auto-mode probe: caught, clean exit 1. Generic-mode pages: per-item error records, crawl continues. Book-mode discovery: honestly, not handled — the exception propagates and crashes; that's the first thing I'd fix." (Verified: main.py 58–61, crawler.py 26.)

**"How do you avoid unnecessary requests?"** — "Cache-first fetch with deterministic URL keys, URL dedupe per run (seen sets), page/link budgets, and re-using the probe fetch — detection results are cached like everything else."

**"How do you handle duplicate URLs?"** — "Book mode: absolute-URL set in the crawler. Generic mode: fragment-stripped set checked at enqueue time. Neither normalizes scheme/host case — a limitation I'd fix with URL normalization at discovery."

**"How does the crawler decide what to visit?"** — "Book mode: only pagination links (`li.next`). Generic mode: BFS over same-domain, robots-allowed, unseen links, bounded by `--max-links` growth and `--pages`."

**"What are the limitations?"** — "Static HTML only (no JS rendering), toscrape-specific selectors in book mode, no retries, no URL normalization beyond fragments, robots 5xx treated as no-rules, and `rating_int`/`availability_normalized` are computed but dropped by the schema."

**"How would you scale it?"** — "Concurrency (thread pool for fetches, with per-host rate limiting), sharded cache, queue-based frontier (Redis) for multi-process crawling, incremental re-crawls keyed by content hash, and structured logging instead of the verbose flag."

**"How would you test it?"** — "Already offline: pure-function tests for normalization, schema tests, CLI mapping tests, the BROKEN_TEST_URL hook for failure injection. Next: mock `Fetcher` with `responses`/`requests-mock` for crawler/extractor integration tests, and a thin smoke test against a local HTTP server."

**"What would you change if you rebuilt it?"** — "httpx + async for concurrent fetches with per-host semaphores, an extraction profile registry instead of toscrape-hardcoded selectors, atomic file writes, a real logging setup, and robots 5xx handled conservatively. Keep: the single-gateway Fetcher pattern, errors-as-data, and per-run output folders — those aged well."

**"Your Pydantic model drops computed fields — why?"** — "Actually a defect, not a choice: `extract_book` computes `rating_int`/`availability_normalized`, but `BookRecord` lacks those fields and Pydantic ignores extras. They never reach books.json. Either add fields or remove the computation — I'd add them."

Full question bank continues in [09_quick_revision.md](09_quick_revision.md).
