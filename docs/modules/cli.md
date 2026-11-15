# Module: `cli.py`

Source: `polite_scraper/cli.py` (192 lines)

## A. Purpose

Translates raw `sys.argv` into (a) a configured `Config` object and (b) a concrete, collision-safe output folder. Also owns the friendly error surface for bad CLI usage.

## B. Imports

```python
import argparse, os, re, sys          # lines 3–6
from pathlib import Path              # line 7
from urllib.parse import urlparse     # line 8
from polite_scraper import __version__  # line 10 — used by --version
from polite_scraper.config import Config  # line 11
```

`re` powers two distinct sanitizers (host → folder name; user answer → folder name). `sys.stdin.isatty()` (line 160) decides whether a collision prompt is interactive. `urlparse` extracts the host for naming.

Note the deferred imports: `ui` is imported *inside* `Parser.error`, `resolve_output_dir`, and `ensure_url_provided` (lines 24, 161, 183) — a lazy-import pattern that avoids a top-level cycle between `ui` and `cli` layers.

## C. Classes and functions

### `class Parser(argparse.ArgumentParser)` (lines 22–28)

Overrides `error(message)`: prints a red `✗` message via `ui.error`, prints `USAGE_EXAMPLES`, raises `SystemExit(2)`. This replaces argparse's default multi-line usage dump with the project's own examples. The `# pragma: no cover` comment documents that it is not unit-tested.

### `build_parser() -> Parser` (lines 31–99)

Defines the CLI surface:

| Argument | Kind | Default | Notes |
|---|---|---|---|
| `url` | positional, `nargs="?"` | `None` | requirement enforced later, not here |
| `--mode` | choice | `auto` | `auto`/`book`/`generic` |
| `--pages` | int | `3` | clamped ≥1 in `build_config` |
| `--max-links` | int | `8` | generic mode only |
| `--delay` | float | `None` | `None` = keep config default |
| `--timeout` | int | `None` | same |
| `--force` | flag | `False` | bypass cache |
| `-v/--verbose` | flag | `False` | flips `ui._VERBOSE` |
| `--version` | action | — | prints `polite-scraper <ver>` and exits |
| `--name` | str | `None` | overrides the site-derived folder name |

`prog="polite-scraper"` matches the console-script name; `RawDescriptionHelpFormatter` preserves the multi-line `USAGE_EXAMPLES` epilog.

### `build_config(args) -> Config` (lines 102–125)

Maps `Namespace` → `Config`:

- URL normalization (106–110): strip whitespace; prepend `https://` if no scheme; append `/` if missing. **No reachability or syntax validation beyond this.**
- `--delay`/`--timeout` only override when explicitly passed (112–115).
- `MAX_CATALOGUE_PAGES = max(1, args.pages)`; `FORCE_REFRESH = args.force`; `MAX_LINKS_PER_PAGE = max(1, args.max_links)` (116–118).
- `USER_AGENT` env var applied last — "CLI flags win" comment refers to the numeric flags; UA comes only from env/default (121–123).

### `derive_run_name(base_url: str) -> str` (lines 128–134)

`urlparse(url).netloc.lower()` → strip `^www\.` → `re.sub(r"[^a-z0-9-]+", "-", host).strip("-")` → fallback `"run"`.

**Verified gap:** the docstring (line 130) says `'https://www.books.toscrape.com/' -> 'books-toscrape'`, but the code keeps the TLD: actual result is `books-toscrape-com`. `tests/test_scraper.py::test_derive_run_name` (lines 131–137) codifies the code's behavior, so the docstring is wrong, not the test.

### `resolve_output_dir(config, explicit_name: str | None) -> Path` (lines 137–179)

1. Sanitize base name: explicit `--name` or derived name; illegal chars → `-` (line 148).
2. `candidate = config.OUTPUT_ROOT / base_name`; if it does not exist → return it (fast path).
3. Collision: loop `suffix = 1, 2, ...` while `OUTPUT_ROOT / f"{base_name}-{suffix}"` exists (155–158).
4. If `sys.stdin.isatty()` is false (CI, pipes): `ui.info` the chosen suffixed name and return it — silent, no overwrite risk.
5. Interactive: `ui.warn` then `input("New folder name [<auto>]: ")` in a loop — empty input accepts the suffix; a nonexistent sanitized name is used; an existing name re-prompts (170–179).

### `ensure_url_provided(args) -> bool` (lines 182–192)

Returns `True` if `args.url` is set; otherwise prints the "No website given." message plus examples and returns `False`. `main.run` converts `False` to exit code `2`.

## D. Execution

`build_parser`/`parse_args` run first in `main()`; `build_config` and `resolve_output_dir` run inside `main.run` (lines 145–146). The `Parser.error` override fires only on bad argv.

## E. Data flow

```text
sys.argv ─► Namespace ─► build_config ─► Config (BASE_URL, delay, timeout, pages, force, max_links)
                                          │
BASE_URL ─► derive_run_name ─────────────┤
--name ──────────────────────────────────┘
                                          ▼
                            resolve_output_dir ─► run_dir Path
                                          ▼
                            main.run sets config.OUTPUT_DIR = run_dir
```

## F. Design decisions

- **What it does:** requirement-checking (`ensure_url_provided`) is deliberately separated from parsing so `--help`/`--version` can exit cleanly through argparse without triggering it.
- **Interpretation:** URL "validation" is intentionally shallow (scheme + trailing slash). Reachability is deferred to the mode-resolution probe, where failures are handled. Keeping folder naming in `cli.py` (not `config.py`) keeps `Config` a dumb settings holder.
- **Interpretation:** the TTY check on collision (line 160) exists because an interactive prompt would hang CI jobs — hence silent auto-suffixing off-TTY.

## G. Interview questions

1. **Why is `url` declared optional if it's required?** So that `--help` and `--version` work without a URL (argparse handles them before our validation runs); `ensure_url_provided` enforces the requirement and produces a friendly message + exit code 2.
2. **How does `--version` work?** `action="version"` with `version=f"%(prog)s {__version__}"`; `__version__` is imported from the package `__init__.py`, so one source of truth feeds both the flag and the packaging metadata (pyproject reads it via `attr`).
3. **Why does `Parser.error` re-raise `SystemExit(2)`?** That is argparse's contract: `parse_args` exits on error; the override just replaces the message. Exit code 2 keeps scripting compatibility with standard argparse behavior.
4. **What happens on the second run against the same site?** `resolve_output_dir` finds `data/runs/<name>` existing, computes the first free `-N` suffix; on a TTY it offers a rename prompt, off-TTY it silently suffixed — a run can never overwrite a previous run's folder.
5. **Why `max(1, args.pages)` instead of trusting the user?** `--pages 0` or negative would otherwise create `while current_url and pages_processed < 0` (never true) in the crawler, or in generic mode skip the loop — the clamp makes behavior defined instead of surprising.
6. **Why is `ui` imported lazily inside functions?** To avoid import-order coupling: `ui` creates a `rich.Console` at module import; deferring keeps `cli` importable in narrow contexts (and mirrors the original code's caution around circulars).
7. **Why keep the TLD in the folder name?** `example.com` and `example.org` are different sites; keeping the TLD (`example-com` vs `example-org`) prevents their runs colliding — a deliberate choice, codified in `test_derive_run_name`.
8. **Is `resolve_output_dir` race-free?** Not fully: between the `exists()` check and folder creation two processes could pick the same suffix. Safe in practice (single user), but the honest answer is "check-then-create, not O_EXCL".

## H. Potential improvements (all tied to code)

1. Docstring drift in `derive_run_name` (line 130) — say `books-toscrape-com`.
2. `USAGE_EXAMPLES` hardcodes `python -m polite_scraper` while the packaged entry point is `polite-scraper` — could pick per invocation.
3. `resolve_output_dir` creates nothing itself; if `ensure_directories` later fails (permissions), the user already answered a prompt for nothing — could probe writability at prompt time.
4. `--name` accepts paths like `..` only after sanitization (`re` strips `.`), which is safe — but the sanitization is implicit; worth a comment.
5. URL scheme handling prepends `https://` even for hosts that are only http (fine for scraping sandboxes, lossy for intranet http-only hosts).
