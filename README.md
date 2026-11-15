# The Polite Scraper

A rate-limited, cache-first web scraper with a terminal UI. It identifies itself with a custom User-Agent, waits at least 500 ms between live requests, caches every downloaded page so re-runs cost the target server nothing, validates all extracted data against Pydantic schemas, and survives broken pages without crashing.

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-10%20passing-brightgreen)](tests/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Release](https://img.shields.io/badge/release-v1.0.0-success)](https://github.com/callmekriztal/polite_scapper/releases/tag/v1.0.0)

```bash
polite-scraper https://books.toscrape.com
```

```
───────────────────────── Discovering catalogue pages ──────────────────────────
  ✓ 3 catalogue pages crawled — 60 unique book URLs

───────────────────── Extracting & validating book details ─────────────────────
  ✓ 60 valid books, 0 rejected

╭──────────────────────────────── Run Summary ─────────────────────────────────╮
│      Requests  0 network / 64 cache                                          │
│ Records saved  60                                                            │
│      Duration  0.772s                                                        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Modes

The target website is the only required argument. The mode can be set explicitly or auto-detected.

**`book`** — built for catalogue-style sites such as [books.toscrape.com](https://books.toscrape.com/). Follows pagination, discovers product links, and extracts per-product: title, price (raw and normalized), availability (raw and structured), rating, description, source page, and timestamp.

**`generic`** — works on any website. BFS-crawls same-domain links (rate-limited, robots.txt-checked) and extracts per-page metadata: title, h1, meta description, headings, same-domain links, image count, and word count.

**`auto`** (default) — fetches the seed page and checks for catalogue markup. Book catalogues use book mode; everything else falls back to generic mode.

## Installation

From a release artifact:

```bash
pipx install polite-scraper
# or
pip install polite_scraper-1.0.0-py3-none-any.whl
```

From source:

```bash
git clone https://github.com/callmekriztal/polite_scapper.git
cd polite_scapper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

When installed, run with `polite-scraper <url>`. From a source checkout, run with `python -m polite_scraper <url>`.

## Usage

```bash
# Book catalogue (auto-detected)
polite-scraper https://books.toscrape.com

# Any other website, deeper crawl
polite-scraper https://quotes.toscrape.com --mode generic --pages 5

# Custom run folder name, bypass cache, verbose logs
polite-scraper example.com --name my-run --force -v
```

Options:

| Flag | Description | Default |
|---|---|---|
| `url` | Website to scrape (required) | — |
| `--mode auto\|book\|generic` | Scraper mode | `auto` |
| `--pages N` | Maximum pages to crawl | `3` |
| `--max-links N` | Generic mode: new same-domain links followed per page | `8` |
| `--delay SEC` | Minimum delay between live requests | `0.5` |
| `--timeout SEC` | Request timeout | `10` |
| `--force` | Ignore the local cache, re-fetch everything | off |
| `--name NAME` | Custom run folder name | derived from the website |
| `-v, --verbose` | Show per-request logs and raw record checkpoints | off |

The `USER_AGENT`, `TIMEOUT`, `MIN_DELAY_SECONDS`, and `BROKEN_TEST_URL` environment variables are also supported; CLI flags take precedence.

## Output

Each run writes to its own folder under `data/runs/`, named after the website:

```
data/runs/
├── books-toscrape-com/
│   ├── books.json
│   ├── errors.json
│   └── run-report.json
└── quotes-toscrape-com/
    ├── pages.json
    ├── errors.json
    └── run-report.json
```

| File | Mode | Contents |
|---|---|---|
| `books.json` | book | Validated product records |
| `pages.json` | generic | Validated page-metadata records |
| `errors.json` | both | Validation and fetch failures, with reasons |
| `run-report.json` | both | Execution metrics (duration, cache hits, record counts) |

If a run folder for the website already exists, the scraper prompts for a new name, or applies an auto-suffix (`-1`, `-2`, ...) when accepted — a run never overwrites another.

<details>
<summary>Example record — books.json</summary>

```json
{
  "title": "A Light in the Attic",
  "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "price_text": "£51.77",
  "price_gbp": 51.77,
  "availability_text": "In stock (22 available)",
  "rating_text": "Three",
  "description": "It's hard to imagine a world without A Light in the Attic. This now-classic collection of poetry and drawings from Shel Silverstein celebrates its 20th anniversary...",
  "source_page": "https://books.toscrape.com/catalogue/page-1.html",
  "fetched_at": "2026-11-15T03:16:34.270989+00:00"
}
```
</details>

<details>
<summary>Example record — pages.json (generic mode)</summary>

```json
{
  "url": "https://quotes.toscrape.com/",
  "title": "Quotes to Scrape",
  "h1": "Quotes to Scrape",
  "meta_description": null,
  "headings": ["Quotes to Scrape", "Top Ten tags"],
  "same_domain_links": ["https://quotes.toscrape.com/login"],
  "link_count": 47,
  "image_count": 0,
  "word_count": 282,
  "fetched_at": "2026-11-15T08:44:55.123456+00:00"
}
```
</details>

## Architecture

```
CLI argument ──> cli.py (argparse, config, run-folder naming)
                     │
                     ▼
                fetcher.py (session, User-Agent, rate limit, disk cache, robots.txt)
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
  crawler.py                generic.py
  (book mode:               (any site: BFS over
   pagination +              same-domain links,
   product URLs)             robots.txt-checked)
        │                         │
        ▼                         ▼
  extractor.py              page extraction
        └────────────┬────────────┘
                     ▼
              validator.py (Pydantic: BookRecord / PageRecord)
                     │
                     ▼
              reporter.py (books.json / pages.json / errors.json / run-report.json)
```

Each stage is isolated: replacing the extractor or target site does not affect the fetch, validation, or reporting layers.

## Testing

```bash
pytest tests/ -v
```

The suite covers price/rating/availability normalization, Pydantic validation failures, broken-page simulation, generic extraction, CLI config mapping, and run-folder collision handling.

## Politeness and ethics

- Identifying `User-Agent` on every request, configurable via `USER_AGENT`
- Minimum 500 ms delay between live requests; cache reads never sleep
- `robots.txt` consulted in generic mode; the run aborts if the agent is disallowed
- Only `200 OK` accepted as a successful response
- Disk caching by default so development re-runs make zero network requests

Do not reuse this tool against a site without checking its rules and terms of service first.

## Documentation

Design decisions, data schema tables, failure-handling hooks, and the internship assignment context are documented in [docs/scraper.md](docs/scraper.md).

## License

[MIT](LICENSE)
