# 05 — Error Handling and Edge Cases

Every scenario below was verified against the code. Each entry states: **handled / not handled**, the exact mechanism (file + line), and what actually happens to the user.

Legend: ✅ handled gracefully · ⚠️ handled with caveats · ❌ not handled (crashes or misbehaves)

## A. Input & configuration errors

| Scenario | Status | Mechanism & behavior |
|---|---|---|
| No URL given | ✅ | `cli.ensure_url_provided` (182–192): friendly message + examples; `main.run` returns 2 (main.py 142–143) |
| Invalid arguments (bad `--mode` value, etc.) | ✅ | custom `Parser.error` (cli.py 22–28): red message + usage examples, `SystemExit(2)` |
| URL missing scheme (`example.com`) | ✅ | `build_config` prepends `https://` (cli.py 106–110) |
| Malformed URL / unreachable DNS | ⚠️ | nothing validates syntax; the auto-probe fetch fails → `ui.error` + `SystemExit(1)` (main.py 44–46). But in explicit `book`/`generic` mode, the same failure is **not** probed first — see below |
| `--pages 0` / negative `--max-links` | ✅ | clamped by `max(1, ...)` (cli.py 116, 118) |
| Invalid `--mode` choice | ✅ | argparse `choices` rejects before `run()` |
| Env var changes after import | ⚠️ | env defaults are read at class-definition time (config.py 7–12); changing `os.environ` later has no effect. Not an error — a semantic quirk worth stating |
| URL that is not a website (e.g. `ftp://...`) | ⚠️ | scheme `ftp` passes normalization; `requests` raises `InvalidSchema` (a `RequestException`) — in auto mode → clean exit 1; in explicit modes → unhandled (❌, same as below) |

## B. Network errors

| Scenario | Status | Mechanism & behavior |
|---|---|---|
| Connection refused / DNS failure during **auto** probe | ✅ | `main.py` 42–46: caught, `ui.error`, exit 1 — the cleanest failure path in the project |
| Same during **book-mode discovery** | ❌ | `CatalogueCrawler.discover_books` has no try/except (crawler.py 26) and `run_book_mode` doesn't wrap it (main.py 58–61). The exception propagates → **full traceback, exit 1 via interpreter**. Verified: this is the largest unhandled path |
| Same during **book-mode extraction** (a detail page) | ✅ | per-item `except Exception` (main.py 98–105): error record `{"product_url", "reason": "Page processing exception: ...", "raw_record": None}`, run continues |
| Same during **generic crawl** (any page) | ✅ | per-item `except Exception` (generic.py 121–125): error record; crawl continues; `pages_fetched` not incremented — failed pages don't consume the budget |
| Timeout (`TIMEOUT` exceeded) | ⚠️ | raises `requests.Timeout` (a `RequestException`): same paths as above — clean in auto-probe/generic/extraction; crash in book discovery |
| HTTP 404 / 500 on any fetched page | ⚠️ | `Fetcher._network_get` raises `HTTPError` (fetcher.py 84–89) — same per-mode paths as above. Generic mode records `Fetch failed: HTTP fetch failed ... status code 404` |
| HTTP 401/403 | ⚠️ | treated identically to 404 — raised, no special-casing |
| Server keeps failing | ⚠️ | **no retries exist** — each failing page is quarantined once; politeness policy |

## C. robots.txt scenarios (generic mode only)

| Scenario | Status | Mechanism & behavior |
|---|---|---|
| robots.txt exists, seed disallowed | ✅ | `check_robots` returns False (generic.py 98–103) → `ui.error` + `SystemExit(1)` (main.py 118–119) |
| robots.txt exists, seed allowed, subpath disallowed | ✅ | `_robots_allows` filters every enqueued link (generic.py 145) — the disallowed path is never fetched |
| robots.txt missing (404) | ✅ | `fetch_robots_txt` returns `None` → "no rules" → proceed (fetcher.py 61–63) |
| robots.txt fetch fails (network error) | ⚠️ | caught → `None` → treated as "no rules" → proceeds (fetcher.py 56–60). Reasonable, but RFC 9309 leans conservative on unreachable robots |
| robots.txt returns 5xx | ⚠️ | same as above — treated as "no rules" (non-200 → None). A conservative implementation would abort or retry |

## D. Content / parsing errors

| Scenario | Status | Mechanism & behavior |
|---|---|---|
| Empty response body (200, blank) | ⚠️ | BeautifulSoup parses empty content fine; book mode: `div.product_main` missing → `ValueError` → error record. Generic mode: `title` = `""` → "No page title found" error record (generic.py 130–135) |
| Malformed/truncated HTML | ⚠️ | `html.parser` is forgiving — best-effort tree; missing elements yield `None`/`""` selectors → handled as above |
| Non-HTML 200 response (PDF, image) | ⚠️ | no Content-Type check (fetcher.py) — parsed as text; yields error records downstream. Wasteful but non-crashing |
| Missing `div.product_main` (site redesign) | ✅ | explicit `ValueError` per page (extractor.py 34–36) → error record "Could not find product_main area..." → run completes with 0 records + N errors |
| Missing price tag | ⚠️ | `price_text = ""` → `normalize_price` raises `ValueError("Price text is empty")` (utils.py 41) → error record |
| Unparseable price text | ✅ | `normalize_price` raises (utils.py 45) → error record |
| Unknown rating word | ✅ | `normalize_rating` → 0 (utils.py 52) — record *accepted* with rating 0 |
| Description missing | ✅ | by design `None` (extractor.py 63–67) — valid record |
| Empty title (generic) | ✅ | quarantined with raw payload preserved (generic.py 130–135) |
| Record fails Pydantic schema (bad URL, negative price...) | ✅ | `RecordValidator` → error dict with `validation_errors` list (validator.py 33–40) |

## E. Crawl-logic edge cases

| Scenario | Status | Mechanism & behavior |
|---|---|---|
| Duplicate URLs across catalogue pages | ✅ | `seen_urls` set (crawler.py 23, 40) |
| Duplicate URLs across generic pages | ✅ | `seen` set, fragment-stripped (generic.py 115, 143) |
| Pagination loop (`li.next` pointing backwards) | ⚠️ | `seen_urls` prevents re-discovery of the same books, but `current_url` could oscillate between two already-visited catalogue pages — `pages_processed` reaches `MAX_CATALOGUE_PAGES` and stops. Bounded, not detected |
| Link to itself (generic) | ✅ | dedupe: seed is in `seen` from the start |
| Relative vs absolute same page (generic) | ⚠️ | fragment-stripping + absolutization catch most; scheme/host-case/trailing-slash variants are *not* normalized — could double-fetch |
| `--max-links` smaller than found links | ✅ | frontier growth guard (generic.py 141) caps enqueue rate (convoluted but bounded) |
| Zero pages fetched (generic, all fail) | ✅ | loop ends when queue exhausts; `ui.checkpoint("Raw Page Sample", {"note": "no pages"})` (main.py 127); `pages.json` = `[]` |

## F. Filesystem errors

| Scenario | Status | Mechanism & behavior |
|---|---|---|
| Cache dir unwritable | ⚠️ | `mkdir(exist_ok=True)` raises `PermissionError` inside `ensure_directories` (config.py 38–40) — first called at `main.run` 148, **before the banner** → raw traceback, crash |
| Cache read error (corrupt file) | ✅ | swallowed (fetcher.py 43–44) → falls back to network |
| Cache write error (disk full mid-run) | ❌ | `cache_path.write_text` (fetcher.py 47) raises → in extraction loop it's caught per-item (main.py 98) — but the *next* fetch will fail again; in discovery it crashes |
| Output dir unwritable | ❌ | `Reporter.save_*` has no try/except (reporter.py 39/55/67) → crash after all scraping work completed — the worst-case timing |
| Run folder collision | ✅ | `resolve_output_dir` auto-suffix or interactive rename (cli.py 150–179); never overwrites |

## G. Process-level

| Scenario | Status | Mechanism & behavior |
|---|---|---|
| Ctrl-C mid-run | ✅ | `main()` catches `KeyboardInterrupt` → `ui.warn` → exit 130 (main.py 216–220) |
| Ctrl-C during `time.sleep` in the rate limiter | ✅ | same handler — `KeyboardInterrupt` interrupts `sleep` |
| Other KeyboardInterrupt subclass / SIGTERM | ❌ | SIGTERM not handled — abrupt termination; no cleanup |
| Unhandled exception anywhere | ⚠️ | Python prints traceback, exit 1. No top-level catch-all exists (deliberate? arguable — see 08) |

## Summary counts

- **Handled gracefully:** 14 scenarios — the per-item extraction/generic loops, validation, robots policy, collisions, argument errors, auto-probe failures.
- **Handled with caveats:** 9 — most notably: robots.txt 5xx as "no rules", no retries, non-HTML responses parsed anyway, env-at-import semantics.
- **Not handled:** 3 real crash paths — (1) book-mode discovery network failure, (2) output/cache write failures, (3) any filesystem error in `Reporter`.

## The interview-ready framing

> "The error philosophy is errors-as-data at the record level and fail-fast at the configuration level. A bad page becomes an entry in errors.json; a bad command line becomes exit code 2 with a friendly message. What I'd fix first: book-mode discovery has no per-page isolation, and the reporter should write atomically — those are the two paths where a real deployment would see a crash."

Cross-refs: [modules/main.md](modules/main.md), [modules/fetcher.md](modules/fetcher.md), [modules/generic.md](modules/generic.md), [modules/reporter.md](modules/reporter.md), [08_improvements_and_roadmap.md](08_improvements_and_roadmap.md).
