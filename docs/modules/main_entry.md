# Module: `__main__.py`

Source: `polite_scraper/__main__.py` (5 lines)

```python
from polite_scraper.main import main

if __name__ == "__main__":
    raise SystemExit(main())
```

## A. Purpose

Makes `python -m polite_scraper <url>` work. This file is what Python executes when a package (rather than a module path) is invoked with `-m`.

## B. Imports

Single import: `main` from `polite_scraper.main`. Importing it executes all of `main.py`'s module-level code — its `sys.path` insert (line 11) and the imports of every other module in the package.

## C. Contents and semantics

- The `if __name__ == "__main__":` guard (line 3) evaluates to `True` **only** when this file is executed as the top-level script — which is exactly what `python -m polite_scraper` does (it runs `__main__.py` under the name `__main__`).
- `raise SystemExit(main())` converts the integer return of `main()` into the process exit code (0/1/2/130 as documented in [main.md](main.md)).
- If someone *imports* `polite_scraper.__main__` directly, the guard is `False` and nothing executes — safe.

## D. Execution

Entry path for `-m`:

```text
$ python -m polite_scraper https://books.toscrape.com
1. Python locates package polite_scraper on sys.path
2. Executes polite_scraper/__init__.py        (defines __version__)
3. Executes polite_scraper/__main__.py as "__main__"
4. __main__.py imports polite_scraper.main    (loads everything)
5. __name__ == "__main__" is True
6. main() runs → SystemExit(code)
```

## E. Data flow

No data of its own — pure delegation to `main()`.

## F. Design decisions

- **What it does:** the thinnest possible `-m` shim: import, guard, exit-code plumbing.
- **Interpretation:** keeping `__main__.py` minimal (instead of holding logic) means there is exactly one implementation of the run lifecycle — `main.py` — used by both `python -m` and the `polite-scraper` console script. No drift is possible between entry points.
- **Fact:** the installed console script (`polite-scraper = polite_scraper.main:main` in `pyproject.toml`) bypasses this file entirely and calls `main()` directly.

## G. Interview questions

1. **What does `python -m X` actually do?** It finds package/module `X` on `sys.path`, executes its `__main__.py` (packages) or the module itself (plain modules) with `__name__ == "__main__"`, adding the *current working directory* to `sys.path` (not the package's own directory).
2. **Why does `__main__.py` need the `if __name__` guard at all?** So that importing `polite_scraper.__main__` as a module doesn't re-trigger a run — the guard distinguishes "executed" from "imported".
3. **What is the difference between this entry and the `polite-scraper` script?** Functionally identical (both call `main()`). Mechanically: `-m` executes `__main__.py` with cwd on `sys.path`; the console script is a generated stub that imports `polite_scraper.main:main` — it does not execute `__main__.py` at all.
4. **Why `raise SystemExit(main())` instead of `sys.exit(main())`?** Equivalent effect; `raise SystemExit(code)` makes the integer → exit-code conversion explicit and avoids needing `import sys` in a file that otherwise doesn't use it.

## H. Potential improvements

1. Could accept no arguments at all (`main()` already parses argv) — it already does; nothing to change.
2. If `main.py`'s sys.path hack (line 11) is ever removed, nothing here needs to change — the shim stays correct either way.
