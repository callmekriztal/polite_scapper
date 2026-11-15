# Module: `validator.py`

Source: `polite_scraper/validator.py` (47 lines)

## A. Purpose

The gate between raw dicts and the data contracts. Converts Pydantic's exceptions into *error data* so the pipeline can continue past bad records — this module is why one malformed page cannot kill a run.

## B. Imports

```python
from typing import Any                                # line 1
from pydantic import ValidationError                  # line 2
from polite_scraper.models import BookRecord, PageRecord  # line 3
```

## C. Class: `RecordValidator` (all static methods)

The class exists only as a namespace; it has no state. Three static methods:

### `validate_record(raw_record: dict) -> tuple[BookRecord | None, dict | None]` (lines 8–11)

Book-mode entry: delegates to `_validate(raw_record, BookRecord, "BookRecord")`.

### `validate_page(raw_record: dict) -> tuple[PageRecord | None, dict | None]` (lines 13–16)

Generic-mode entry: delegates to `_validate(raw_record, PageRecord, "PageRecord")`.

### `_validate(raw_record, model: type, label: str) -> tuple[Any | None, dict | None]` (lines 18–47)

The core contract:

```python
try:
    validated = model.model_validate(raw_record)   # line 31
    return validated, None
except ValidationError as ve:                      # line 33
    error_details = {
        "product_url": raw_record.get("product_url") or raw_record.get("url"),
        "reason": f"{label} Schema Validation Failed",
        "validation_errors": ve.errors(include_url=False),
        "raw_record": raw_record,
    }
    return None, error_details
except Exception as ex:                            # line 41
    error_details = {..., "reason": str(ex), "raw_record": raw_record}
    return None, error_details
```

Details worth citing precisely:

- The error dict's URL key is always `product_url`, populated from whichever raw key exists (line 35) — this is why `ui.errors_table` can read a single key for both modes (ui.py 132).
- `ve.errors(include_url=False)` strips Pydantic's documentation-link noise from each error entry; the full list of per-field failures lands in `errors.json` — a debugging goldmine.
- The second `except Exception` is a safety net: any unexpected error *inside validation* becomes data rather than a crash. In practice it rarely fires (validation failures are `ValidationError`s), but it makes the function total — it cannot raise.
- Never returns both halves truthy: the tuple invariant is `(record, None)` or `(None, details)`.

## D. Execution

Called per record from `main.run_book_mode` (main.py 93) and `main.run_generic_mode` (main.py 131). Tested directly by `tests/test_scraper.py::test_invalid_record_validation` (lines 34–50) and `test_generic_page_validation_rejects_empty_title` (95–113).

## E. Data flow

```text
raw dict ─► _validate ─┬─► (BookRecord, None)      ─► main accumulates → reporter.save_books
                       └─► (None, error dict)      ─► main accumulates → reporter.save_errors → errors.json
                                                          └─► ui.errors_table (first 5 shown)
```

## F. Design decisions

- **What it does:** total function; errors-as-data; label-parameterized so one core serves two schemas.
- **Interpretation:** returning tuples instead of raising lets the caller (`main.py` 93–97) decide accumulation policy in one place; raising would scatter try/except through the pipelines.
- **Interpretation:** keeping `raw_record` inside the error payload means `errors.json` is self-sufficient — you can diagnose *why* a record failed without re-fetching the page (and with the disk cache, re-parsing costs nothing).

## G. Interview questions

1. **Why catch `ValidationError` instead of letting it propagate?** One bad record must not kill a 60-page run (assignment requirement: broken-page resilience). Converting it to data lets `main` accumulate it into `errors.json` and continue.
2. **What does `ve.errors(include_url=False)` give you?** A list of per-field failures (loc, msg, type) — structured enough to debug schemas without re-running. `include_url=False` omits the link to Pydantic docs from every entry.
3. **Why is the URL key always `product_url` even for pages?** So downstream consumers (`ui.errors_table` line 132, any BI tooling) need one schema for both modes. Line 35 does `raw_record.get("product_url") or raw_record.get("url")`.
4. **Is the second `except Exception` reachable?** Barely — e.g. a `model_validate` hook crashing on bizarre input. It exists to guarantee the function is total; in a code review you'd call it a belt-and-braces catch with a cost: it can mask real bugs as "validation errors".
5. **Why static methods instead of module functions?** Style choice mirroring the original AI-generated structure (`docs/AI-VS-ME.md`); functionally identical to free functions — honest answer if pressed: the class adds no state or polymorphism here.
6. **How do you test validation without network?** Feed handcrafted dicts: `tests/test_scraper.py` 34–50 (negative price, empty title → rejected with matching `product_url`) and 95–113 (empty page title → rejected). No mocking needed because the validator is pure.

## H. Potential improvements

1. `model: type` typing is loose — `type[BaseModel]` communicates intent.
2. The catch-all `except Exception` (line 41) should log the exception type distinctly (e.g. prefix the reason) so masked bugs are visible in `errors.json`.
3. The `product_url` fallback key logic could move into the callers, keeping `_validate` single-schema.
4. Duplicate raw records in `errors.json` when the same URL fails repeatedly (generic mode revisits are deduped, so currently bounded) — fine, but worth a sentence.
5. Consider a dataclass/TypedDict for `error_details` — it is currently an implicitly-shaped dict consumed by `ui.errors_table` and `reporter.save_errors`.
