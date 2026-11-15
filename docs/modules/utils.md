# Module: `utils.py`

Source: `polite_scraper/utils.py` (75 lines)

## A. Purpose

Pure functions: URL→absolute, URL→cache filename, and the three normalizers (price, rating, availability) plus text cleaning. No I/O, no state — the most testable module in the project, and the one with the most direct test coverage.

## B. Imports

```python
import hashlib                      # line 1 — MD5 for cache filenames
import re                           # line 2 — parsing price/quantity/URL patterns
from typing import Optional         # line 3
from urllib.parse import urljoin    # line 4
```

## C. Module constant

```python
RATING_MAP = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}  # lines 6–13
```

The site encodes ratings as CSS class words; this maps them. Unknown words → 0 (handled by `normalize_rating`'s `.get(clean, 0)`).

## D. Functions

### `make_absolute_url(base_url: str, relative_url: str) -> str` (15–17)

One-line `urljoin(base, rel)`. Semantics worth knowing cold:
- `urljoin("https://x.com/catalogue/page-1.html", "book_1/index.html")` → `https://x.com/catalogue/book_1/index.html`
- A leading `/` in `rel` anchors to the host root: `urljoin(base, "/about")` → `https://x.com/about`
- Used by `crawler.py` 38/51 and `generic.py` 56.

### `url_to_cache_filename(url: str) -> str` (19–36)

Deterministic cache keys — the same URL must always map to the same filename:

1. `re.search(r"catalogue/page-(\d+)\.html", url)` → `catalogue-page-N.html` (22–24).
2. The exact strings `https://books.toscrape.com/` and `.../index.html` → `catalogue-page-1.html` (25–26) — the site's root is catalogue page 1 for caching purposes.
3. `/catalogue/<slug>/index.html` → `detail-<slug[:30]>-<md5(url)[:8]>.html` (29–33) — readable + collision-resistant: the 8-hex hash disambiguates slugs that truncate identically.
4. Anything else → `detail-<full-md5>.html` (35–36) — the generic-mode path (which is why generic cache files carry the slightly misleading `detail-` prefix).

### `normalize_price(price_text: str) -> float` (38–45)

- Empty → `ValueError("Price text is empty")`.
- `re.search(r"(\d+\.\d+|\d+)", text)` → first numeric group as float.
- No match → `ValueError(f"Could not parse numeric price from '{text}'")`.

**Behavioral subtlety (verified):** the regex ignores sign and thousands separators. `"£-10"` → `10.0` (the minus is skipped), `"1,234.56"` → `234.56` (the comma splits the match). Negative prices are only ever rejected by *Pydantic* (`price_gbp: ge=0.0`), and only if the negative value reaches it as an already-float field — which the extractor's normalizer prevents by stripping the sign first. Test `test_price_normalization` (tests 15–20) covers the happy paths and the `ValueError`, not the sign subtlety.

### `normalize_rating(rating_text: str) -> int` (47–52)

Empty → 0; `RATING_MAP.get(clean, 0)` — unknown words safely map to 0 rather than raising.

### `normalize_availability(availability_text: str) -> dict` (54–68)

Empty → `{"in_stock": False, "quantity": 0, "raw": ""}`.
Otherwise: `in_stock = "in stock" in clean.lower()`; quantity from `\((\d+)\s+available\)` (case-insensitive); if in stock but no explicit count → quantity 1; if out of stock → 0. Returns `{"in_stock", "quantity", "raw"}`.

### `clean_text(text: Optional[str]) -> Optional[str]` (70–75)

`" ".join(text.strip().split())` — collapses all whitespace runs to single spaces and trims; empty results become `None`. Used by both extractors; it is the reason multi-line titles/descriptions in raw HTML come out as single-line strings.

## E. Data flow

```text
crawler/generic ─► make_absolute_url
fetcher ─────────► url_to_cache_filename
extractor ───────► normalize_price/rating/availability + clean_text
generic ─────────► clean_text
tests ───────────► all of the above (directly)
```

## F. Design decisions

- **What it does:** stateless transforms, fail-loud price parsing, fail-soft rating parsing.
- **Interpretation:** `ValueError` for a missing price but `0` for an unknown rating encodes a business rule: a record without a usable price is invalid; a record without a rating is merely degraded.
- **Interpretation:** MD5 (not SHA) for cache keys — pre-image resistance is irrelevant for local cache naming; MD5 is fast and short enough to read. Hashing the full URL guarantees uniqueness; the slug prefix is purely for human browsing of `data/cache/`.

## G. Interview questions

1. **Why `urljoin` instead of string concatenation for links?** Handles every relative form (`../x`, `/x`, `//host/x`, full URLs) per RFC 3986; concatenation breaks on any of these.
2. **How does `url_to_cache_filename` guarantee determinism?** Pure function of the URL string: regex branches then MD5. Same URL → same filename on every run/machine.
3. **Why does a cache filename embed both a slug and a hash?** Readability (you can identify a cached page by eye) + uniqueness (two long titles truncated to the same 30 chars differ in the 8-hex digest).
4. **What does `normalize_price("£-10")` return and why?** `10.0` — the regex `(\d+\.\d+|\d+)` matches the first digit run and ignores the minus sign. If asked "is that a bug?": it's a blind spot — the sign is unrecoverable, so negative prices can't be *detected* at this layer; only a stored negative float would trip Pydantic.
5. **Why does `normalize_availability` default quantity to 1 when "In stock" has no count?** Fact: line 62's `(1 if in_stock else 0)`. Interpretation: "in stock" implies at least one; the raw text is preserved in `raw` for later re-parsing.
6. **Why is `clean_text` so central?** HTML text nodes carry indentation/newlines from markup; every field that becomes a JSON string goes through it. `" ".join(s.split())` is the idiomatic whitespace-normalization idiom.
7. **Where would these functions break first on a non-English site?** `RATING_MAP` (English words), the availability regex (`(N available)` English phrasing), and price parsing (comma decimal separators) — all site-locale-coupled by design to the toscrape sandbox.

## H. Potential improvements

1. `normalize_price` should capture an optional leading minus and/or currency-aware parsing — today's sign-stripping is a silent data transformation.
2. `url_to_cache_filename`'s `detail-` prefix mislabels generic-mode pages (utils.py 35–36) — rename to `page-` for non-catalogue URLs.
3. `RATING_MAP` reversed lookup (`normalize_rating` inverse) doesn't exist — fine, but note ratings are one-way in the dataset.
4. `clean_text` can't distinguish "missing" (`None`) from "present but empty" (`""` → `None`) — by design, but worth documenting at the call sites that care.
5. No unit tests exist for `url_to_cache_filename` or `normalize_availability` (covered only indirectly) — easy wins.
