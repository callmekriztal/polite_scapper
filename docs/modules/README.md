# Modules Index

One document per source module. Read in roughly the order the code executes:

| Module doc | Source file | One-line role |
|---|---|---|
| [init.md](init.md) | `polite_scraper/__init__.py` | Package identity; `__version__ = "1.0.1"` |
| [main_entry.md](main_entry.md) | `polite_scraper/__main__.py` | Enables `python -m polite_scraper` |
| [main.md](main.md) | `polite_scraper/main.py` | Orchestration: mode resolution, pipelines, metrics |
| [cli.md](cli.md) | `polite_scraper/cli.py` | Argument parsing, config mapping, run-folder naming |
| [config.md](config.md) | `polite_scraper/config.py` | Settings dataclass, paths, env defaults |
| [fetcher.md](fetcher.md) | `polite_scraper/fetcher.py` | The single network gateway: cache, rate limit, robots.txt |
| [crawler.md](crawler.md) | `polite_scraper/crawler.py` | Book-mode pagination crawler |
| [extractor.md](extractor.md) | `polite_scraper/extractor.py` | Book-mode HTML parsing + normalization |
| [generic.md](generic.md) | `polite_scraper/generic.py` | Generic mode: BFS + page metadata |
| [models.md](models.md) | `polite_scraper/models.py` | Pydantic contracts |
| [validator.md](validator.md) | `polite_scraper/validator.py` | Validation → (record \| error dict) |
| [reporter.md](reporter.md) | `polite_scraper/reporter.py` | JSON persistence |
| [ui.md](ui.md) | `polite_scraper/ui.py` | Rich terminal output |
| [utils.md](utils.md) | `polite_scraper/utils.py` | Pure helpers (URLs, normalization, cleaning) |
