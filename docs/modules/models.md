# Module: `models.py`

Source: `polite_scraper/models.py` (60 lines)

## A. Purpose

The data contracts. Two Pydantic v2 models define exactly what a *valid* scraped record is. Nothing else defines validation rules; the rest of the package either produces dicts (extractors) or consumes validated models (reporter).

## B. Imports

```python
from datetime import datetime                       # line 1 — ISO timestamp parsing
from typing import Optional                         # line 2
from pydantic import BaseModel, Field, HttpUrl, field_validator  # line 3
```

## C. Classes

### `class BookRecord(BaseModel)` (lines 5–30)

| Field | Type | Constraint |
|---|---|---|
| `title` | `str` | `min_length=1` + custom non-empty validator |
| `product_url` | `HttpUrl` | must parse as an absolute URL |
| `price_text` | `str` | raw, e.g. `£51.77` |
| `price_gbp` | `float` | `ge=0.0` |
| `availability_text` | `str` | raw |
| `rating_text` | `str` | raw word, e.g. `Three` |
| `description` | `Optional[str]` | `None` allowed |
| `source_page` | `HttpUrl` | catalogue page provenance |
| `fetched_at` | `str` | must parse via `datetime.fromisoformat` |

Validators:

- `validate_title_non_empty` (16–21): rejects whitespace-only strings, stores `v.strip()`. Note: the `Field(min_length=1)` and the validator overlap; the validator is stronger (`"   "` passes `min_length=1` but fails the strip check).
- `validate_iso_timestamp` (23–30): `datetime.fromisoformat(v)` inside try/except; re-raises as `ValueError(f"Invalid ISO-8601 timestamp: {v}")` **chained with `from e`** — exception chaining you can point at in an interview. Note it validates *parseability*, not that the timestamp is UTC.

**Extra-fields behavior (verified):** the model declares no `model_config`; Pydantic v2 defaults to ignoring unknown keys. So the `rating_int` / `availability_normalized` keys produced by `extract_book` (`extractor.py` 86–90) are silently dropped at validation. `books.json` contains exactly the nine declared fields.

### `class PageRecord(BaseModel)` (lines 33–60)

Generic-mode contract:

| Field | Type | Constraint |
|---|---|---|
| `url` | `HttpUrl` | page address |
| `title` | `str` | `min_length=1` + non-empty validator |
| `h1`, `meta_description` | `Optional[str]` | nullable |
| `headings` | `list[str]` | default `[]` via `default_factory=list` |
| `same_domain_links` | `list[str]` | default `[]` — the ≤50-entry sample |
| `link_count`, `image_count`, `word_count` | `int` | `ge=0` |
| `fetched_at` | `str` | ISO parseability |

Same two validators as `BookRecord` (46–60) — duplicated code, deliberate observation: three blocks are copy-pasted between the models.

## D. Execution

Imported and used only through `validator.py` (`BookRecord.model_validate` / `PageRecord.model_validate`) and serialized via `reporter.py` (`r.model_dump(mode="json")`, line 37). Never imported by extractors — extractors speak dicts.

## E. Data flow

```text
extractor/generic raw dicts
        ▼ validator.py model_validate
BookRecord / PageRecord instances
        ▼ reporter.py model_dump(mode="json")
plain JSON-safe dicts ─► books.json / pages.json
```

`model_dump(mode="json")` matters: `HttpUrl` objects serialize as plain strings (verified in real output), `datetime`-compatible strings pass through unchanged.

## F. Design decisions

- **What it does:** validation-at-the-boundary; raw scraping stays untyped until the gate.
- **Interpretation:** `HttpUrl` for `product_url`/`source_page`/`url` guarantees the dataset contains only absolute, parseable URLs — a cheap, high-value invariant for downstream consumers.
- **Interpretation:** `price_gbp: float = Field(ge=0.0)` pushes the "price must be sane" rule into the schema, so no consumer ever sees a negative price — even if a future extractor bypasses `normalize_price`.
- **Fact:** raw text fields (`price_text`, `availability_text`, `rating_text`) are preserved *alongside* normalized ones — the dataset keeps both evidence and interpretation.

## G. Interview questions

1. **Why Pydantic instead of plain dicts or dataclasses?** Runtime validation with declarative constraints (`ge`, `min_length`, custom validators), rich error messages (`ValidationError.errors()` with per-field paths — used directly in `errors.json` via `validator.py` 37), and type-safe serialization (`model_dump(mode="json")`).
2. **What is `HttpUrl`?** A Pydantic special type: the value must be a valid absolute URL, and it validates/parses on assignment. It fails records like `"not-a-url"` before they reach storage.
3. **How do unknown fields behave and why does it matter?** Pydantic v2 default ignores extras. Consequence verified: `extract_book`'s `rating_int`/`availability_normalized` are dropped. If the intent were to store them, they'd need fields here (or `model_config = ConfigDict(extra="forbid")` to make them an error).
4. **Why validate `fetched_at` as a string instead of a `datetime` type?** Fact: the field is `str` with a parseability validator (23–30). Design effect: the stored JSON keeps the *exact* original ISO string (including its `+00:00` offset), instead of a re-serialized canonical form.
5. **Why does `title` need both `min_length=1` and a strip validator?** `" "` passes `min_length` but is meaningless; the strip validator catches it and normalizes. Demonstrates layered constraints.
6. **What is `field_validator` and why `@classmethod`?** Pydantic v2's decorator replacing v1 `validator`; the `@classmethod` is required by the API for class-level validators.
7. **What happens when validation fails — exception or value?** Both, by design of `validator.py`: `ValidationError` is *caught* there and converted into an error dict (validator.py 33–40). The model raises; the validator is the shock absorber.
8. **How do the two models differ?** `BookRecord` = product-level (price, rating, availability); `PageRecord` = page-level metadata (headings, counts). Two contracts because two modes produce fundamentally different shapes — a single "record" model would need 50% optional fields.

## H. Potential improvements

1. The two validators are duplicated (16–21/23–30 vs 46–51/53–60) — extract a shared mixin/base model.
2. Add `rating_int`/`availability_normalized` fields or remove their computation upstream (the dead-data path).
3. `fetched_at` could be `datetime` + `model_dump(mode="json")` — same JSON, stronger typing in code.
4. Consider `model_config = ConfigDict(extra="forbid")` to turn dropped-field surprises into loud errors during development.
5. `headings`/`same_domain_links` have no length caps in the schema — the cap lives in the extractor (generic.py 49, 74); the contract could encode it.
