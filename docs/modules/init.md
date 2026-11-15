# Module: `__init__.py`

Source: `polite_scraper/__init__.py` (2 lines)

```python
"""The Polite Scraper — a rate-limited, cache-first web scraper."""

__version__ = "1.0.1"
```

## A. Purpose

Marks the directory as an importable Python package and carries the single source of truth for the version string.

## B. Imports

None. No side effects beyond defining a docstring and one variable.

## C. Contents

- Module docstring (line 1).
- `__version__ = "1.0.1"` (line 2).

## D. Execution

- **Every** `import polite_scraper...` executes this file first (Python package semantics). That happens on: `python -m polite_scraper` (via `__main__.py`), the `polite-scraper` console script, and every test file's imports.
- The version value is consumed in three places:
  1. `cli.py` line 10: `from polite_scraper import __version__` → `--version` flag output.
  2. `pyproject.toml`: `[tool.setuptools.dynamic] version = { attr = "polite_scraper.__version__" }` — the wheel/sdist metadata is generated from this attribute at build time.
  3. PyPI release identity (1.0.1 published via the trusted-publishing workflow).

## E. Data flow

Outbound only: `__version__` → CLI flag, package metadata, PyPI. Nothing flows in.

## F. Design decisions

- **What it does:** deliberately *not* a facade. Some projects re-export their API from `__init__.py`; this one imports nothing, so importing the package is instant and has no dependency side effects (no `Console` creation, no env reads).
- **Interpretation:** keeping the version in `__init__.py` (rather than duplicating it in pyproject) means one bump updates `--version`, built distributions, and PyPI in lockstep — verified working by the v1.0.1 release.

## G. Interview questions

1. **What runs when Python imports a package?** The package's `__init__.py` executes *before* any submodule import completes; here that's just a docstring and `__version__`.
2. **Why is the version here and not in `pyproject.toml`?** Single source of truth: pyproject *reads* it via `attr = "polite_scraper.__version__"` at build time (dynamic version). `--version` and PyPI metadata cannot drift.
3. **What breaks if you delete `__init__.py`?** The directory stops being a regular package; `python -m polite_scraper` and all `from polite_scraper...` imports fail (with namespace-package behavior it *may* still import depending on path setup — but the declared, reliable behavior is lost).
4. **Why does `__init__.py` not import the CLI for convenience?** Importing `main` would pull `requests`, `bs4`, `rich` and create module-level state on *every* package import (including metadata-reading tools like pip/setuptools during builds). Keeping it dependency-free makes builds and `--version` cheap.

## H. Potential improvements

1. Could add `__all__` if it ever grows exports — currently unnecessary.
2. A `build`/`release` docstring section is absent but unneeded while the file stays this small.
