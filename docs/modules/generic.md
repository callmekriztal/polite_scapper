# Module: `generic.py`

Source: `polite_scraper/generic.py` (153 lines)

## A. Purpose

Generic mode — scraping sites that are *not* book catalogues. Two responsibilities in one module: a breadth-first crawler over same-domain links (`GenericSiteScraper`) and a selector-agnostic page-metadata extractor (`GenericExtractor`). The mode is also the one that enforces robots.txt.

## B. Imports

```python
from collections import deque                      # line 7 — BFS queue
from datetime import datetime, timezone            # line 8 — fetched_at
from urllib.parse import urljoin, urlparse         # line 9 — note: urljoin is imported but unused
from bs4 import BeautifulSoup                      # line 11
from polite_scraper import ui                      # line 13
from polite_scraper.config import Config           # line 14
from polite_scraper.fetcher import Fetcher         # line 15
from polite_scraper.utils import clean_text, make_absolute_url  # line 16
```

**Verified gap:** `urljoin` (line 9) is imported but never used — all URL joining goes through `utils.make_absolute_url`, which itself wraps `urljoin`.

## C. Classes and functions

### `class GenericExtractor` (lines 19–79)

Class attribute `HEADING_TAGS = ["h1"..."h6"]` (line 22).

**`extract_page(self, page_url: str, html_content: str) -> dict`** (24–79) — pure parsing, no I/O, never raises (except on absurd input):

1. Title (28–31): `soup.title` text; if absent/empty → first `<h1>`; if still nothing → `""` (the record will be rejected later — this is the *deliberate* empty-title path).
2. `h1_text` (34–35): first `<h1>`, may be `None`.
3. Meta description (38–41): `meta[name=description]` `content` attribute.
4. Headings (44–50): `find_all(HEADING_TAGS)`, cleaned, non-empty, **stops at 10**.
5. Same-domain links (53–60): for every `<a href>`: absolutize (`make_absolute_url`), parse, keep only `parsed.netloc == origin.netloc` and scheme in (`http`, `https`); strip `#fragments`; per-page dedupe via `dict.fromkeys` (preserves order).
6. Word count (63–66): `soup(["script", "style", "noscript"])` → `.decompose()` (removes from the tree), then `get_text(separator=" ", strip=True)` and `len(text.split())`.
7. Return dict (68–79): url, title, h1, meta_description, headings, `same_domain_links[:50]` (sample), full `link_count`, `image_count`, `word_count`, `fetched_at` (UTC ISO).

Subtlety worth knowing: `same_domain_links` (max 50) and `link_count` (full count) are two different fields — the sample is stored, the true count is reported.

### `class GenericSiteScraper` (lines 82–153)

**`__init__(self, config, fetcher, extractor=None)`** (85–89): default-extractor pattern enables injection for tests; `self.robots_parser = None` until checked.

**`check_robots(self, start_url: str) -> bool`** (91–103):

- Base = `scheme://netloc` (93).
- `self.robots_parser = self.fetcher.fetch_robots_txt(base)` — `None` means "no robots.txt / unreachable" → `ui.info("... proceeding politely anyway")` → `True`.
- `can_fetch(self.config.USER_AGENT, start_url)` → `ui.success` or `ui.error` + return the boolean.
- `main.run_generic_mode` (main.py 117–119) converts `False` into `SystemExit(1)`.

**`scrape(self) -> tuple[list[dict], list[dict]]`** (105–148) — the BFS:

```python
queue: deque[str] = deque([start_url])       # line 114
seen: set[str] = {start_url.split("#")[0]}   # line 115 — fragment-insensitive dedupe from the start
```

Loop `while queue and pages_fetched < max_pages` (118):

1. `url = queue.popleft()` (119) — FIFO = breadth-first.
2. `fetcher.fetch(url)` inside try/except `Exception` (121–125): failure → `{"url", "reason": "Fetch failed: ..."}` error record + `continue`. **Note:** `pages_fetched` is *not* incremented on failure — a dead page does not consume budget.
3. `extract_page` (128).
4. Empty title → error record `{"url", "reason": "No page title found (skipped record)", "raw_record": raw}` (130–135) — page content is preserved in the error for forensics. Otherwise → `raw_records`.
5. **Enqueue phase** (139–146): for each same-domain link: the guard at line 141 — `if pages_fetched + len(queue) >= max_pages and len(queue) >= max_links: break` — stops adding once the queue is already large enough to hit the page cap; then `if link not in seen` → add to `seen` → `if self._robots_allows(link)` → `queue.append(link)`.
   - Honest reading: the guard is convoluted. Its *net effect* is that each page contributes at most ~`max_links` new links once the queue is near saturation; before saturation it contributes all its links. The simplest truthful description in an interview: "we cap the frontier growth using both `--max-links` per page and the global `--pages` budget."
6. Return `(raw_records, error_records)`.

**`_robots_allows(self, url: str) -> bool`** (150–153): `True` when no parser (no rules); else `can_fetch(USER_AGENT, url)` — so **every** enqueued link, not just the seed, is robots-checked.

## D. Execution

Driven by `main.run_generic_mode` (main.py 115–124): `check_robots` first (abort path), then `scrape()` under an indeterminate progress spinner.

## E. Data flow

```text
config.START_URL / MAX_PAGES / MAX_LINKS_PER_PAGE
        ▼
check_robots ─► fetcher.fetch_robots_txt ─► RobotFileParser | None
        ▼
BFS loop:
  queue ─► fetcher.fetch ─► html
                 └─ failure ─► error_records
        ▼
GenericExtractor.extract_page ─► raw dict (10 fields)
        ├─ title empty ─► error_records (with raw)
        └─ else ─► raw_records ─► RecordValidator.validate_page ─► PageRecord
```

## F. Design decisions

- **What it does:** BFS (FIFO deque), same-domain only, fragment-insensitive dedupe, robots-checked enqueues, budget-capped frontier.
- **Interpretation:** restricting to same-domain links (line 58) is the classic "polite crawler" boundary — following external links would turn a site scrape into an unbounded web crawl.
- **Interpretation:** robots.txt is enforced at two levels — the seed page (hard abort) and every link (filter) — because a site may disallow subpaths but allow the root.
- **Fact:** dedupe happens at *enqueue* time (`seen`), so a page linked from two different pages is fetched once.
- **Fact:** extraction here never touches the network — only `GenericSiteScraper` does.

## G. Interview questions

1. **Why BFS (deque) instead of DFS (stack)?** BFS with a `--pages` budget approximates "important pages first" (closer to the entry point, usually more navigational/canonical) and gives deterministic, reproducible crawls for a page cap. DFS would dive into one branch and return unrepresentative pages.
2. **How do you decide what to visit?** Three filters: same `netloc` (extractor, line 58), not in `seen` (line 143), and `_robots_allows` (line 145). The frontier additionally respects `--max-links` growth guard and the global `--pages` budget.
3. **Is robots.txt enforced for every URL or just the seed?** Every URL: seed via `check_robots` (abort), each candidate link via `_robots_allows` (line 145). The parser is fetched once and reused.
4. **What happens if a page fetch fails mid-crawl?** Error record + `continue` (121–125); the crawl continues; `pages_fetched` is *not* incremented, so failed pages don't consume the page budget — meaning the run may fetch up to `max_pages` *successful* pages.
5. **Why does `extract_page` return `""` instead of raising for a missing title?** So the *crawler* decides the record's fate (error record with the raw payload preserved) rather than the parser — keeps parsing total and policy centralized (lines 130–135).
6. **Why `dict.fromkeys(same_links)` for dedupe?** Preserves insertion order (Python 3.7+ dict guarantee) while removing duplicates — a set would lose order; `list(dict.fromkeys(...))` is the idiom.
7. **Why cap `same_domain_links` at 50 but keep the true `link_count`?** Bounded record size for JSON storage; the count still reflects reality. A hub page with 5,000 links stores 50 URLs and `link_count: 5000`.
8. **Why `decompose()` scripts/styles before counting words?** Otherwise JavaScript blobs and CSS inflate `word_count` massively; `decompose` mutates the soup — done *after* link extraction so `<a href>` inside scripts is irrelevant anyway.
9. **What are the loop guards' exact semantics?** `while queue and pages_fetched < max_pages` bounds total pages; line 141's guard bounds frontier growth per page once the queue is large; `max_links` is per-page *in saturation*, not a strict per-page cap before saturation — be precise about this if asked to trace it.

## H. Potential improvements

1. Remove the unused `urljoin` import (line 9).
2. Replace the convoluted guard (line 141) with explicit logic: `new_links = [l for l in raw["same_domain_links"] if l not in seen][:max_links]` — clearer and strictly per-page.
3. Dedupe should also normalize scheme/host case and strip trailing slashes (currently `/page` vs `/page/` are distinct).
4. No depth limit: with `--pages 500` the BFS can wander deep; a `depth` per entry would give better control.
5. `check_robots` checks only the *exact* start URL; deep links to disallowed subpaths are caught by `_robots_allows`, but a start URL explicitly disallowed by path still gets a single warning then `SystemExit(1)` — correct, but a retry with "allowed parent path" suggestion would be friendlier.
6. robots.txt 5xx is treated as "no rules" (fetcher.py 61–63) — RFC 9309 leans conservative; a distinction between 404 (no file) and 5xx (temporarily unavailable) would be more correct.
