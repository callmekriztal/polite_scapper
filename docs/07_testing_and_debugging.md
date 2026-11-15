# 07 — Testing and Debugging

## 1. What exists: the real test suite

`tests/test_scraper.py` (162 lines) — **10 tests, all offline** (zero network, zero mocking libraries). Run:

```bash
pytest tests/ -v          # from repo root, with venv active
```

Verified output: `10 passed`.

| Test (line) | Verifies | Mechanism |
|---|---|---|
| `test_price_normalization` (15) | `normalize_price`: `£51.77`→51.77, `£ 19.99`→19.99, `100`→100.0, and `ValueError` on non-numeric | direct calls to `utils.normalize_price` |
| `test_rating_normalization` (22) | `One`→1, `Three`→3, `Five`→5, unknown→0 | `utils.normalize_rating` |
| `test_missing_description_becomes_none` (28) | `clean_text(None/"")/"   "`→None, `" Valid text "`→"Valid text" | `utils.clean_text` |
| `test_invalid_record_validation` (34) | empty title + `price_gbp=-10.0` → `(None, error)` with matching `product_url` | `RecordValidator.validate_record` with a handcrafted dict |
| `test_broken_detail_page_simulation` (52) | `BROKEN_TEST_URL` hook raises before any network; message contains "Simulated broken page error" | `Config` with tmp paths + hook, `BookExtractor.extract_book`, `pytest.raises` |
| `test_generic_extractor_basic_page` (69) | title/h1/meta extraction, same-domain filter (external `example.org` excluded), image/word counts | `GenericExtractor.extract_page` on an inline HTML string |
| `test_generic_page_validation_rejects_empty_title` (95) | empty page title → `(None, error)` | `RecordValidator.validate_page` |
| `test_cli_build_config` (116) | URL scheme/trailing-slash normalization, pages/max-links clamping, delay/timeout/force mapping | `build_parser().parse_args([...])` → `build_config` |
| `test_derive_run_name` (131) | host → `books-toscrape-com`, www-stripping, path ignored | `cli.derive_run_name` |
| `test_output_dir_auto_suffix_on_collision` (140) | first run plain name; second run `-1`; explicit name collision → `-1` | `cli.resolve_output_dir` with `tmp_path` OUTPUT_ROOT |

Infrastructure facts:
- `sys.path.insert(0, parent.parent)` at the top (lines 3–5) makes `polite_scraper.*` importable without installation.
- `tmp_path` fixtures isolate filesystem effects (tests 52–55, 140–146).
- `test_output_dir_auto_suffix_on_collision` accepts a `monkeypatch` fixture **but never uses it** — verified code smell.
- The suite tests `Config`, `CatalogueCrawler`/`BookExtractor`/`Fetcher` imports (lines 7–13) — `CatalogueCrawler` is imported but **never used in a test** (verified; only `BookExtractor` and `Fetcher` are exercised in test_broken).

## 2. What is NOT tested (honest list)

- `Crawler.discover_books` (pagination logic) — needs network or a mock; untested.
- `GenericSiteScraper.scrape()` (BFS loop, robots checks) — untested.
- `Fetcher` itself (cache behavior, rate limiter, robots parsing) — untested; `test_broken` constructs one but never calls `fetch`.
- `Reporter` (JSON writing), `ui` (rendering), `main.run` orchestration, `resolve_mode_and_start` — untested.
- `url_to_cache_filename`, `normalize_availability` — covered only indirectly (via nothing, actually) — gaps.

## 3. How to run the project (all verified commands)

```bash
# From source
source venv/bin/activate
python -m polite_scraper https://books.toscrape.com                  # book mode (auto-detected)
python -m polite_scraper https://quotes.toscrape.com --mode generic --pages 4
python polite_scraper/main.py https://books.toscrape.com             # direct-script entry

# Installed (PyPI v1.0.1)
pipx install polite-scraper
polite-scraper https://books.toscrape.com --version

# Tests
pytest tests/ -v

# Deterministic offline failure injection
BROKEN_TEST_URL="https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html" \
  python -m polite_scraper https://books.toscrape.com
# → that one book becomes an error record; the other 59 succeed

# Force fresh fetches (ignores cache)
python -m polite_scraper https://books.toscrape.com --force
```

## 4. How to debug individual modules

**Pure modules — REPL first.** `utils.py`, `validator.py`, `models.py`, `extractor.py` (parsing part), `generic.py` (extractor part) have no hidden state:

```python
from polite_scraper.utils import url_to_cache_filename, normalize_price
url_to_cache_filename("https://books.toscrape.com/catalogue/foo_1/index.html")
# 'detail-foo_1-c2b3b31a.html'

from polite_scraper.validator import RecordValidator
RecordValidator.validate_record({"title": "", "product_url": "x", "price_gbp": -1, "fetched_at": "bad"})
# → (None, {...  'validation_errors': [...]})  — inspect validation_errors for per-field reasons
```

**Stateful modules — script with a temp config:**

```python
import tempfile
from pathlib import Path
from polite_scraper.config import Config
from polite_scraper.fetcher import Fetcher
from polite_scraper.crawler import CatalogueCrawler

cfg = Config()
tmp = Path(tempfile.mkdtemp())
cfg.CACHE_DIR, cfg.OUTPUT_DIR, cfg.OUTPUT_ROOT = tmp/"c", tmp/"o", tmp/"r"
cfg.BASE_URL = "https://books.toscrape.com/"
cfg.START_URL = cfg.toscrape_start_url()
f = Fetcher(cfg)
d = CatalogueCrawler(cfg, f).discover_books()
print(d.catalogue_pages_count, len(d.book_urls))
```

Use `--pages 1` equivalent (`cfg.MAX_CATALOGUE_PAGES = 1`) to keep it fast.

## 5. How to trace execution

1. **Verbose mode** — the built-in tracer: `-v` prints every cache hit/fetch with byte sizes (`ui.debug` from fetcher.py 41/78/93), robots.txt outcomes, and the first raw record as a JSON panel (`ui.checkpoint`).
2. **Breakpoints** — `python -m pdb -m polite_scraper https://books.toscrape.com --pages 1`, then set breakpoints: `b polite_scraper/fetcher.py:80` (before session.get), `b polite_scraper/main.py:153` (mode resolution), `b polite_scraper/validator.py:31` (model_validate).
3. **Print tracing** — the fastest for a single question: add temporary prints in `main.run` between stages; the stage rules in the UI already segment the timeline.
4. **Watch the counters** — `fetcher.cache_hits` / `fetcher.network_fetches` tell you instantly whether a problem is I/O or parsing: expect `network=0` on warm runs.

## 6. How to inspect HTTP responses & failures

- Raw responses are cached on disk: `data/cache/*.html` — open the exact file `url_to_cache_filename(url)` predicts, and you are looking at the bytes that were parsed.
- `errors.json` carries per-record diagnostics: validator failures include the full `validation_errors` list *and* the `raw_record`; extraction failures include the reason string.
- To see live traffic: `python -m polite_scraper <url> -v --force` — verbose + forced refresh shows every network fetch.
- For header/body inspection beyond that, add a temporary `print(response.headers)` in `fetcher._network_get` (line 80) — there is no built-in traffic logger.

## 7. How to identify which component failed

Failure locus → evidence:

| Symptom | Where to look |
|---|---|
| traceback mentioning `discover_books` | book-mode discovery network failure (verified unhandled path, main.py 61) |
| `errors.json` entry with `validation_errors` key | Pydantic schema failure (validator.py 33–40) |
| `reason: "Page processing exception: ..."` | fetch/selector/normalize error in extraction (main.py 101–104) |
| `reason: "Fetch failed: ..."` | generic-mode page fetch (generic.py 124) |
| `reason: "No page title found (skipped record)"` | generic extraction produced empty title (generic.py 131) |
| `reason: "Could not find product_main area..."` | site markup changed (extractor.py 36) |
| exit 1 + "robots.txt disallows" | generic mode politeness abort (main.py 118) |
| exit 2 | bad argv or missing URL |

## 8. Test cases that should be added (prioritized)

1. **`Fetcher.fetch` with mocked HTTP** (`responses`/`requests-mock`): 200→cached file created; second call→cache hit; 404→`HTTPError`; `--force` bypass. Highest-value missing test.
2. **`CatalogueCrawler.discover_books` with two fixture pages**: dedupe, `li.next` termination, page cap.
3. **`GenericSiteScraper.scrape`**: BFS order, same-domain filtering, enqueue caps, robots denial paths.
4. **`url_to_cache_filename`**: all four branches (catalogue regex, root special-case, slug+hash, generic md5).
5. **`normalize_availability`**: in-stock with count, without count, out-of-stock.
6. **`resolve_mode_and_start`**: probe finds `product_pod` → book; not found → generic; fetch raises → SystemExit(1).
7. **`Reporter`**: writes four files into `config.OUTPUT_DIR`; `HttpUrl` serialized as string.
8. **`--version` flag** (added in 1.0.1) and the `Parser.error` override.

## 9. How to test modules independently / mock network

- The dependency-injection seams make this direct: `GenericSiteScraper(config, fetcher, extractor=FakeExtractor())` accepts an injected extractor (generic.py 85–88).
- To fake the network, build a `FakeFetcher` with the same `fetch`/`fetch_robots_txt` signatures and pass it anywhere a real `Fetcher` goes — every consumer receives it via constructor.
- Without adding libraries, `unittest.mock.patch.object(Fetcher, "fetch", return_value=("<html>...", False))` works for quick cases.
- With libraries: `responses` (requests-level) or `httmock`; point them at toscrape fixtures saved from `data/cache/` — the cache doubles as a fixture store.
- The `BROKEN_TEST_URL` hook (config.py 32, extractor.py 26–27) remains the zero-dependency failure injector.
