# Module: `ui.py`

Source: `polite_scraper/ui.py` (137 lines)

## A. Purpose

Every character of terminal output flows through here. It centralizes the `rich` Console and implements the project's verbosity policy: **quiet and polished by default; detailed per-request logs and raw-record checkpoints only with `-v`**.

## B. Imports

```python
import json                    # line 8 — VERIFIED UNUSED (nothing in the file references json.*)
from typing import Any         # line 9
from rich.console import Console          # line 11
from rich.json import JSON                # line 12 — checkpoint rendering
from rich.panel import Panel              # line 13 — banner/checkpoint/summary containers
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn, TimeElapsedColumn)  # lines 14–22
from rich.table import Table              # line 23 — summary/files/errors tables
```

## C. Module-level state (lines 25–27)

```python
console = Console()   # line 25 — the single output channel for the whole app
_VERBOSE = False      # line 27 — module-global flag
```

Two module globals instead of a class — every importer (`main`, `cli`, `fetcher`, `generic`, `reporter`) shares this one state. `set_verbose` (30–32) mutates it; `is_verbose` (35–36) reads it.

**Verified gap:** `is_verbose()` is never called anywhere in the package. `debug`/`checkpoint` read `_VERBOSE` directly.

## D. Functions

### Log-level printers (39–58)

| Function | Prefix | Behavior |
|---|---|---|
| `debug(message)` | none | `console.log(message)` **only if `_VERBOSE`** — rich timestamps included |
| `error(message)` | red `✗` | always |
| `warn(message)` | yellow `!` | always |
| `info(message)` | cyan `›` | always |
| `success(message)` | green `✓` | always |

### `stage(title)` (61–63)

Blank line + `console.rule` — the section dividers ("Discovering catalogue pages", "Done").

### `make_progress() -> Progress` (66–77)

Factory for the project's standard progress bar: spinner + description + bar + % + `MofNCompleteColumn` + elapsed. Key option: **`transient=True`** (76) — the bar erases itself when done, which is why the default output shows clean stage summaries without leftover bars. Callers use `total=None` for indeterminate crawling and a real total for extraction (`main.py` 60, 78).

### `banner(target_url, mode, pages, delay, cache_dir, run_dir)` (80–96)

`Panel` with the run's configuration. Pure display; called once per run (`main.py` 155–162).

### `checkpoint(title, data: dict)` (99–103)

`Panel(JSON.from_data(data))` — a syntax-highlighted JSON panel. **No-op unless `_VERBOSE`** (101–102). Used for the discovery stats and the first raw record (`main.py` 67–70, 84–91) — the "show me the actual scraped payload" debugging affordance.

### `summary_table(rows: list[tuple[str, Any]])` (106–112)

Two-column `Table` (label right-aligned bold, value plain) inside a cyan panel. Generic — the rows come from `main.run` (195–202).

### `files_table(files: list[tuple[str, str]])` (115–121)

Same shape; lists the three written paths.

### `errors_table(errors: list[dict], limit: int = 5)` (124–137)

- Returns silently if `errors` is empty (126) — "no error spam on clean runs".
- Red `Table` with title `Errors (N)`, columns `#`, `URL / Item`, `Reason`.
- URL key lookup: `err.get("product_url") or err.get("url") or "?"` (132) — supports both error-dict shapes (validator-style `product_url`, generic-fetch-style `url`).
- Shows first `limit` entries; if more, prints `"... and N more (see errors.json)"` (136–137).

## E. Data flow

```text
main.run: set_verbose(args.verbose) ─► _VERBOSE flag
All modules: ui.debug/info/success/error/warn ─► console (filtered by flag)
main: banner / stage / make_progress / checkpoint / *_table ─► console
```

The module never reads files or network — output only.

## F. Design decisions

- **What it does:** one Console, one verbosity flag, semantic printers instead of raw `print`.
- **Interpretation:** centralizing output was required to *make* the default-quiet behavior possible — `Fetcher` logs were converted from unconditional `print()` calls to `ui.debug` (see `docs/AI-VS-ME.md` history and `fetcher.py` 41/59/78/93).
- **Interpretation:** `transient=True` is a deliberate UX choice: progress is for *while it runs*, the summary panels are for *after*. Mixing both would leave terminal clutter.
- **Fact:** `ui.console.print` is also used directly by `cli.py` (187, 191) for the missing-URL message — the singleton makes ad-hoc formatting possible anywhere.

## G. Interview questions

1. **How is verbosity implemented?** A module-global `_VERBOSE` set once by `main.run` via `ui.set_verbose` (ui.py 30–32). `debug` and `checkpoint` check it; everything else prints unconditionally.
2. **Why a module global instead of passing a logger around?** Trade-off honestly stated: globals are testable-hostile and hidden coupling, but here the flag is set exactly once at startup and every module already needs *some* output path; a `Console` parameter on every call would swamp signatures. If asked "what would you change": a small `Logger` object injected via constructor would be the refactor.
3. **What does `transient=True` do and why?** The `Progress` display is erased after completion (line 76) — the final screen shows only stage rules and summary panels.
4. **Why does `errors_table` cap at 5?** Terminal readability; the authoritative full list is `errors.json` (the function even says so at line 137). `limit` is a parameter, so callers could raise it.
5. **Why does `checkpoint` render JSON through rich rather than `print(json.dumps(...))`?** `rich.json.JSON` gives syntax highlighting and indentation for free, and it's gated behind verbose — keeping default output clean.
6. **Which functions are dead code?** `is_verbose()` (never called) and the `import json` (never referenced). Both verified against the package.

## H. Potential improvements

1. Remove `import json` (line 8) and either use or remove `is_verbose()`.
2. `errors_table` assumes the error dict shape (`product_url`/`url`, `reason`) — a shared `ErrorRecord` TypedDict in `models.py` would contract it.
3. No file logging: `-v` output is ephemeral; a `--log-file` writing the debug stream would help post-mortems.
4. `banner`'s hard-coded column alignment (`Target      `) uses manual spacing — `rich.table` inside the panel would align automatically.
5. Consider a `--quiet` mode suppressing even success/info lines for scripted use.
