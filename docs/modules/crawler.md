# Module: `crawler.py`

Source: `polite_scraper/crawler.py` (59 lines)

## A. Purpose

Book-mode discovery: walk the catalogue's pagination and collect every unique product URL. It deliberately does *not* extract product data — that separation (discovery vs. extraction) is the module's reason to exist.

## B. Imports

```python
from bs4 import BeautifulSoup                       # line 1
from polite_scraper.config import Config            # line 2
from polite_scraper.fetcher import Fetcher          # line 3
from polite_scraper.utils import make_absolute_url  # line 4
```

## C. Classes and functions

### `class DiscoveryResult` (lines 6–10)

Plain class (not a dataclass) with three attributes set in `__init__`:

| Attribute | Type | Meaning |
|---|---|---|
| `catalogue_pages_count` | `int` | how many catalogue pages were fetched |
| `discovered_count` | `int` | raw link count before dedupe (equal to `len(book_urls)` in practice since dedupe happens during append) |
| `book_urls` | `list[dict]` | entries `{"product_url": str, "source_page": str}` |

Interpretation: `discovered_count` is redundant with `len(book_urls)` — it exists because the original assignment required reporting both "discovered" and "unique" counts; the current code reports both as the same number.

### `class CatalogueCrawler`

**`__init__(self, config, fetcher)`** (15–17): stores both dependencies (injected by `main.run_book_mode`, main.py 55).

**`discover_books(self) -> DiscoveryResult`** (19–59) — the pagination walker:

```python
while current_url and pages_processed < self.config.MAX_CATALOGUE_PAGES:   # line 25
```

1. `html_content, _ = self.fetcher.fetch(current_url)` (26) — cache-aware, rate-limited, may raise `HTTPError` (see error handling below).
2. `soup = BeautifulSoup(html_content, "html.parser")` (29).
3. `product_pods = soup.select("article.product_pod")` (33) — the book cards on books.toscrape.com.
4. Per card (34–45): `pod.select_one("h3 a")`; if the anchor exists *and* has `href`, `make_absolute_url(current_url, href)` converts the relative link; the `seen_urls` set dedupes; entry appended with the current catalogue page as `source_page` (provenance).
5. Pagination (48–53): `soup.select_one("li.next a")`; if present with `href` → `current_url = make_absolute_url(current_url, next_rel)`; else `current_url = None` → loop ends.
6. Return `DiscoveryResult(...)` (55–58).

Selectors are site-specific to books.toscrape.com: `article.product_pod`, `h3 a`, `li.next a`. There is **no** fallback selector set.

### Error handling

None inside the module — no try/except at all. Consequences, verified:

- `fetcher.fetch` raising `HTTPError` (non-200 catalogue page) or `RequestException` (network failure) propagates up through `run_book_mode` → `run` → `main`, and **crashes the run with a traceback** (only KeyboardInterrupt is caught in `main`, main.py 218).
- Malformed HTML never raises: `select`/`select_one` return empty results, so the crawler simply finds fewer books, and a missing `li.next` terminates the walk gracefully.

This asymmetry (network failure = crash; HTML failure = silent under-collection) is the module's most important characteristic to know cold.

## D. Execution

Instantiated and driven only by `main.run_book_mode` (main.py 55, 61), inside the discovery stage with an indeterminate progress spinner (`ui.make_progress`, total=None).

## E. Data flow

```text
config.START_URL ─► discover_books()
                        │  fetch(current_url) ─► Fetcher
                        │  urljoin via utils.make_absolute_url
                        ▼
        DiscoveryResult.book_urls: [{"product_url", "source_page"}]
                        │
                        ▼
        main.run_book_mode loop ─► BookExtractor.extract_book(product_url, source_page)
```

`source_page` travels all the way into `BookRecord.source_page` (models.py 13) — provenance survives to the final dataset.

## F. Design decisions

- **What it does:** loop-until-no-next, page cap, in-order discovery, set-based dedupe.
- **Interpretation:** separating discovery from extraction means the expensive extraction stage can be re-run against the same discovery list, and a cache-first discovery makes re-runs free.
- **Interpretation:** the `MAX_CATALOGUE_PAGES` cap exists for politeness (don't crawl 50 pages when told to crawl 3) — the while-condition (line 25) stops *after* processing, so passing `--pages 3` fetches exactly 3 pages, then stops even if `li.next` exists.
- **Fact:** dedupe is per-run (`seen_urls` is a local set); two runs share nothing — the disk cache is what prevents re-fetching, not the dedupe.

## G. Interview questions

1. **How does the crawler know when to stop?** Two independent stops: the `li.next a` selector disappears (natural end of pagination), or `pages_processed` reaches `MAX_CATALOGUE_PAGES` ( politeness cap). Both checked per iteration at line 25.
2. **How are duplicate URLs avoided?** A `seen_urls: set` (line 23) checked before appending (line 40). Relative-vs-absolute duplicates collapse because `make_absolute_url` normalizes before the check.
3. **What URL normalization happens?** Only `urljoin` (utils.py 15–17). No scheme normalization, no query/fragment stripping (unlike generic mode's fragment stripping) — two URLs differing only in `#fragment` would be treated as distinct here.
4. **What happens if page 2 of the catalogue returns 404?** `Fetcher._network_get` raises `HTTPError`; `discover_books` has no try/except; the exception propagates and kills the run. Honest answer: discovery-stage failures are not handled; extraction-stage failures are.
5. **Why is `DiscoveryResult` a plain class instead of returning a tuple?** Named fields make call sites self-documenting (`discovery.book_urls`); it also mirrors the "results object" pattern used by `RunMetrics`. A frozen dataclass would be the modernization.
6. **Why `html.parser` and not `lxml`?** Zero extra dependency (pure-stdlib parser); slower on big pages but the target pages are small, and the project pins no C-extension dependencies.
7. **Why store `source_page` per URL?** Provenance: `BookRecord.source_page` records which catalogue page surfaced the product — useful for debugging discovery and for resumable crawls.
8. **What if a `product_pod` has an `<h3>` without an `<a>`, or an `<a>` without `href`?** Line 36's condition (`a_tag and a_tag.get("href")`) skips it silently — malformed cards are simply not discovered.

## H. Potential improvements

1. Wrap the per-page fetch in try/except and record failed pages into the run's error list instead of crashing (matches the per-item resilience used in extraction).
2. Normalize URLs (strip fragments, lowercase scheme/host) before dedupe to catch more duplicates.
3. `DiscoveryResult` → `@dataclass(frozen=True)`.
4. The `discovered_count` attribute duplicates `len(book_urls)` — either track true pre-dedupe count or drop it.
5. Selector constants (`"article.product_pod"`, `"li.next a"`) should be module-level constants or config, to make site adaptation explicit.
