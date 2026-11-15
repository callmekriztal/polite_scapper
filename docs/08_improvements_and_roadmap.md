# 08 — Limitations, Improvements & Roadmap

All items are tied to actual code. Priority = (user impact × likelihood) ÷ effort. Trade-offs are stated; nothing here recommends tech for its own sake.

## Verified defects (fix first)

| # | Defect | Location | Impact | Fix & trade-off |
|---|---|---|---|---|
| D1 | **Book-mode discovery crashes on network failure** — no try/except around `fetcher.fetch` in the pagination loop | `crawler.py` 26, uncaught in `main.run_book_mode` (58–61) | A single failing catalogue page kills the whole run with a traceback — the exact failure mode the rest of the codebase carefully avoids | Wrap per-page fetch in try/except, collect error records, continue/abort gracefully. Cost: none; ~10 lines. **Top priority.** |
| D2 | **Reporter crashes on write failure after all work is done** | `reporter.py` 39/55/67 (no try/except) | Disk full / permissions → traceback after scraping completed; results lost from terminal (cache survives) | try/except → `ui.error` + distinct exit code. Optional atomic writes: write `.tmp`, `os.replace`. Cost: small. |
| D3 | **Computed fields silently dropped** — `rating_int`, `availability_normalized` never reach `books.json` | produced at `extractor.py` 86–90; absent from `models.py` 5–14; Pydantic ignores extras | Misleading: code suggests the dataset contains them | Either add both fields to `BookRecord` (data gain) or remove the computation (honesty gain). Adding is better — data's already there. |
| D4 | **robots.txt fetch bypasses politeness & metrics** | `fetcher.py` 57 (`session.get` directly) | One unrated request per generic run; `network_fetches` undercounts | Route through the rate limiter or note it explicitly. Trivial. |
| D5 | **robots.txt 5xx treated as "no rules"** | `fetcher.py` 61–63 (non-200 → None) | RFC 9309 leans conservative: a temporarily failing robots.txt should not be read as permission | Distinguish 404 (proceed) from 5xx (warn loudly, proceed-or-abort flag). Small change, politeness win. |
| D6 | Docstring drift: `derive_run_name` example says `books-toscrape` | `cli.py` 130 (actual: `books-toscrape-com`) | Interview/reading confusion | One-line docstring fix. |
| D7 | Dead code: `reporter` params unused in both mode runners; `ui.is_verbose()` never called; `import json` unused in ui.py; `urljoin` imported unused in generic.py; unused `CatalogueCrawler` import in tests; unused `monkeypatch` fixture | `main.py` 53/113, `ui.py` 8/35, `generic.py` 9, `tests/` 8/140 | Reading cost, lint noise | One cleanup commit. Zero risk. |

## Code quality

- **Naming honesty:** `RunMetrics.links_discovered` actually counts validated+failed+broken records (`main.py` 184) — rename to `records_processed` or compute real link counts. `Fetcher`'s generic cache prefix `detail-` mislabels generic pages (`utils.py` 35–36).
- **Type tightening:** `model: type` → `type[BaseModel]` (validator.py 21); `tuple[list, list, dict]` → typed generics (main.py 53/113).
- **Dead-simple wins:** constants for selectors (`crawler.py` 33/35/48) to make site adaptation explicit; remove magic `50`/`10` caps in `generic.py` into named constants.
- **Console-script awareness:** `USAGE_EXAMPLES` (cli.py 15–18) shows `python -m polite_scraper` even for installed users — show `polite-scraper` when `sys.argv[0]` is the console script.

## Architecture

- **Extraction profiles.** Book selectors are hardcoded toscrape selectors (`extractor.py` 34–62, `crawler.py` 33–48). A `Profile` protocol (`catalogue_selector`, `next_selector`, `product_parser`) would let book mode target other catalogue sites without touching the pipeline. Trade-off: real abstraction cost; only worth it if a second catalogue site is a goal. Generic mode already covers "anything else".
- **Error taxonomy.** Error dicts currently have two shapes (`product_url` vs `url` keys — validator.py 35, generic.py 124). One `ErrorRecord` TypedDict/dataclass shared by both modes removes consumer guesswork (`ui.errors_table` line 132 already works around it).
- **UI injection.** `ui` is a module global (ui.py 25–27). Fine at this size; a `Console`/`Logger` object injected via constructors would enable tests to assert output. Trade-off: signature noise everywhere — defer until output assertions are actually needed.

## Performance

Current bottlenecks are honest to name and cheap to reason about:

1. **Serial fetching** — every request waits for the previous + 0.5 s. 60 books ≈ 30 s minimum on cold cache. *Fix: thread pool (e.g. 4 workers) with a per-host semaphore; the rate limiter must become lock-aware. Trade-off: complexity + politeness risk; the politeness story is the product — cap concurrency low.*
2. **Full-parse word count** — `get_text()` on every page (generic.py 65). Fine at hundreds of pages; at 100k pages, switch parser to `lxml` (one dependency, ~5–10× parse speed) and/or count words lazily.
3. **In-memory record accumulation** — all records live in lists until save (main.py 94/133). At 100k+ records, stream to NDJSON. Not needed at current scope.

## Reliability

- **Retries with backoff** for GETs on 5xx/timeouts only (never 4xx). Trade-off: retries can hammer a struggling server — cap at 2, honor Retry-After, keep it *behind* the rate limiter. Current stance ("fail fast, record, continue") is defensible and should remain the default.
- **Atomic output writes** (see D2) — `os.replace` after full write.
- **Content-Type guard** — reject non-`text/html` 200s before parsing (fetcher.py) — saves pointless parses on stray links.
- **URL normalization** at discovery (lowercase scheme/host, strip fragments — fragments already stripped in generic mode only; trailing slashes and host case are not normalized anywhere).

## Security

- **SSRF scope:** the crawler follows same-domain links only in generic mode, but `--mode book`/auto-probe will fetch *any* user-supplied URL, including internal addresses (`http://localhost/...`, metadata endpoints). For a tool run by developers on their own machines this is acceptable; for a hosted deployment it is an SSRF hole. Mitigation if ever hosted: resolve and block private IP ranges.
- **No code execution risk:** no `eval`/`exec`, `pickle` — the codebase parses HTML only. JSON outputs are written, never executed.
- **Auth/sensitive pages:** generic mode will scrape pages behind cookie-less "logins" (e.g. `quotes.toscrape.com/login` appears in its link list) — it fetches whatever the site serves; no credential handling exists (by design).
- **Data trust:** outputs are untrusted scraped text; consumers should treat `books.json` as data, not markup. Fine as-is.

## Maintainability

- **Docs drift risk:** `docs/scraper.md` still describes the assignment-era structure in places; this documentation set (01–09) is current for 1.0.1. Keep docs updated per release — cheap now, expensive later.
- **Env-at-import semantics** (config.py 7–12): subtle; a one-line comment exists in this docset — consider moving reads into `build_config` for testability.
- **Test debt:** crawler and generic crawler untested ([07_testing_and_debugging.md](07_testing_and_debugging.md) §8 lists the exact cases). The DI seams (constructor injection) already support this — the only real cost is writing fakes.

## Testing

Priority order mirrors §8 of doc 07: fetcher-with-mock first (it gates crawler+extractor tests), then crawler pagination fixtures, then generic BFS. The `BROKEN_TEST_URL` hook shows the intended pattern — extend it rather than replacing it.

## User experience

- **`--version` exists; `--version`-style self-checks** could add `--dry-run` (plan the crawl: show start URL, robots verdict, page budget, then exit) — cheap, high value for trust.
- **`--output`-style JSON Lines option** for large runs.
- **Exit codes:** completed runs with quarantined errors exit 0 (main.py 210). Consider `0 = clean, 1 = completed with errors, 2+ = fatal` — trade-off: scripts currently treating 0-with-errors as success would break; document loudly if changed.
- **Progress detail:** the extraction bar could show `cache` vs `network` split live (counters exist on the Fetcher).

## Recommended sequencing

1. **Now (one commit):** D1, D2, D4, D6, D7 — correctness + dead code. ~1 hour.
2. **Next release:** D3 (schema fields), D5 (robots 5xx), fetcher mock tests, URL normalization at discovery.
3. **When scale matters:** concurrency (per-host limiter), lxml, NDJSON streaming, retry/backoff.
4. **Only if a second catalogue site is real:** extraction profiles.

The refusal list (things deliberately NOT recommended): headless browsers (no JS-rendered target), Celery/queues (single-machine tool), click/typer (argparse suffices), a database (JSON outputs are the feature).
