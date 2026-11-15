# Module: `extractor.py`

Source: `polite_scraper/extractor.py` (92 lines)

## A. Purpose

Book-mode parsing: turn one product detail page's HTML into one normalized record dict. Owns all book-specific CSS selectors and calls `utils.normalize_*` for the typed conversions.

## B. Imports

```python
from datetime import datetime, timezone   # line 1 — fetched_at timestamp
import requests                           # line 2 — only for raising HTTPError (test hook, line 27)
from bs4 import BeautifulSoup             # line 3
from polite_scraper.config import Config  # line 4
from polite_scraper.fetcher import Fetcher  # line 5
from polite_scraper.utils import (clean_text, normalize_availability,
                                  normalize_price, normalize_rating)  # lines 6–11
```

`requests` here is *not* used for HTTP — it is imported solely so the broken-page simulation hook can raise a `requests.HTTPError` (line 27). Worth saying in an interview: an import used only for its exception type.

## C. Class: `BookExtractor`

### `__init__(self, config, fetcher)` (lines 16–18)

Dependency injection from `main.run_book_mode` (main.py 56). Only `config.BROKEN_TEST_URL` and `fetcher.fetch` are actually consumed.

### `extract_book(self, product_url: str, source_page: str) -> dict` (lines 20–92)

**Raises:** `requests.HTTPError` (test hook), `requests.HTTPError`/`RequestException` (fetch), `ValueError` (missing `product_main`, unparseable price).

1. **Test hook** (26–27): if `config.BROKEN_TEST_URL` equals `product_url`, raise immediately — before any network activity. This is what makes `test_broken_detail_page_simulation` deterministic and offline.
2. `fetched_at = datetime.now(timezone.utc).isoformat()` (29) — captured *before* the fetch; the timestamp records when extraction began, not when the response arrived.
3. `html_content, _ = self.fetcher.fetch(product_url)` (30) — the second element (`was_cached`) is intentionally ignored.
4. `soup = BeautifulSoup(html_content, "html.parser")` (31).
5. **`div.product_main` is required** (34–36): missing → `ValueError(f"Could not find product_main area in {product_url}")`. This is the module's structural sanity check: everything else is nested inside this container.
6. Field selectors (39–67):

| Field | Selector | Notes |
|---|---|---|
| title | `div.product_main h1` | `clean_text(...)` or `""` |
| price_text | `p.price_color` | e.g. `£51.77` |
| availability_text | `p.instock.availability` | e.g. `In stock (22 available)` |
| rating_text | `p.star-rating` class list | the class that isn't `star-rating`, lowercased comparison, e.g. `Three` |
| description | `#product_description` + `find_next_sibling("p")` | `None` if header or paragraph missing — the only optional field |

   Rating extraction detail (53–59): iterates `class` attribute list, takes the first class whose lowercase form is not `"star-rating"`. So `class="star-rating Three"` yields `"Three"`. If the tag is missing → `""` (→ later normalizes to rating 0).
7. **Raw record** (70–79): dict with title, product_url, price_text, availability_text, rating_text, description, source_page, fetched_at.
8. **Normalization** (82–84) → `price_gbp: float`, `rating_int: int`, `availability_normalized: dict` merged into the dict (86–90).

### The dropped-fields fact (must-know)

`extract_book` returns `rating_int` and `availability_normalized`, but `BookRecord` (`models.py` lines 5–14) has no such fields. Pydantic v2's default behavior **ignores unknown keys**, so after `RecordValidator.validate_record`, these two values exist nowhere — they are absent from `books.json` (verified against actual output: a record contains exactly the nine schema fields). The computation at lines 82–84 therefore currently serves only to *validate indirectly* (a bad price raises `ValueError` → error record) — but note `normalize_price` failures raise before Pydantic ever runs, while `rating_int`/`availability_normalized` failures cannot fail at all (they return 0/dict).

## D. Execution

Called 60× (or `--pages`-dependent) from the loop in `main.run_book_mode` (main.py 82). Exceptions are caught per iteration (main.py 98) and converted to error records.

## E. Data flow

```text
discovery entry {"product_url", "source_page"}
        ▼
fetcher.fetch(product_url) ─► html (cache or network)
        ▼
BeautifulSoup ─► selectors ─► raw dict {8 fields}
        ▼
utils.normalize_price/rating/availability ─► +3 derived fields
        ▼
RecordValidator.validate_record ─► BookRecord (9 fields; extras dropped)
```

## F. Design decisions

- **What it does:** page-scoped, selector-driven, normalize-at-source.
- **Interpretation:** "normalize at extraction time" (rather than inside the model) mirrors the original assignment's Stage 4 ("normalize price_gbp, rating, and string fields") and keeps the Pydantic model a *contract for storage*, not a transformer.
- **Interpretation:** the required `div.product_main` check converts "page changed" into an explicit, typed failure rather than 9 silent empty-field records.
- **Interpretation:** the description selector (`#product_description` + next `<p>` sibling) is deliberately tolerant — descriptions are optional and their absence is `None`, not an error.

## G. Interview questions

1. **Walk me through one `extract_book` call.** Test-hook check → timestamp → fetch (cache-aware) → parse → required container check → six selectors → raw dict → three normalizations → return dict. Callers catch everything.
2. **How is the rating extracted?** The rating lives in a CSS *class* (`class="star-rating Four"`), not text. `rating_tag.get("class", [])` is scanned for the first class ≠ `star-rating` (lines 54–59), then `normalize_rating` maps the word to 1–5 (`RATING_MAP` in utils.py).
3. **Why does `normalize_price` raising make a record "failed" while a missing rating doesn't?** Price is a required, semantically critical field; `normalize_price` raises `ValueError` on unparseable text (utils.py 41–45), which the orchestrator records as a broken page. Missing rating normalizes to 0 — a *valid but poor* record. Design choice: price failure invalidates the record; rating absence degrades it.
4. **What happens to `rating_int` and `availability_normalized`?** They are computed (lines 82–90) but dropped by `BookRecord` validation, because Pydantic v2 ignores unknown keys by default and the schema has no fields for them. Verified against `books.json` output. Honest answer: dead data as of 1.0.1.
5. **Why capture `fetched_at` before the fetch?** Fact: line 29 runs before `fetcher.fetch` (line 30). It marks extraction-start time; with warm caches the difference is negligible, on network fetches the timestamp slightly precedes data receipt. Consistency, not precision, is the goal.
6. **What happens when the site changes `product_main` to `product-hero`?** Line 36 raises `ValueError` per page → every page becomes an error record with reason "Could not find product_main area..." — the run completes with 0 records and N errors, which is the correct loud failure mode.
7. **Why import `requests` if you never make requests?** Only for the exception type in the test hook (line 27). Alternative: define a local exception — but reusing `HTTPError` keeps callers (main.py 98) with a single catch.

## H. Potential improvements

1. Add `rating_int` and `availability_normalized` to `BookRecord` (or stop computing them) — remove the dead-data path.
2. Selectors as module constants for testability/adaptation.
3. `find_next_sibling("p")` grabs the *first* following paragraph — if the site inserts an ad paragraph before the description, the wrong text is captured; a `find_next` on a more specific container would be sturdier.
4. `fetched_at` could be captured after fetch for accuracy of "when we had the data".
5. Consider a soup strategy: reusing a single parser string is fine, but `extract_book` re-parses per page — fine at this scale, measurable at 10k+ pages.
