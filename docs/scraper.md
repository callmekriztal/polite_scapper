# The Polite Scraper — FlyRank Internship Backend Track W5 A9

A production-grade, polite web scraper in Python 3.10+. It ships two modes: a **book mode** targeting [Books to Scrape](https://books.toscrape.com/) (catalogue crawling + product extraction) and a **generic mode** that scrapes any website you pass on the command line. Both feature local HTML caching, BeautifulSoup parsing, Pydantic validation, error resilience, structured reporting, and a polished `rich` terminal UI.

---

## Stage 0 — Target Classification

- **Target URL**: [https://books.toscrape.com/](https://books.toscrape.com/)
- **Scope**: First 3 catalogue pages (`catalogue/page-1.html`, `page-2.html`, `page-3.html`), yielding exactly 60 book detail URLs.
- **Data Collected**:
  - `title` (raw string)
  - `product_url` (absolute URL)
  - `price_text` (raw string, e.g., `"£51.77"`)
  - `availability_text` (raw string, e.g., `"In stock (22 available)"`)
  - `rating_text` (raw string, e.g., `"Three"`)
  - `description` (raw string or `null`)
  - `source_page` (catalogue page URL where discovered)
  - `fetched_at` (ISO-8601 UTC timestamp)
- **Why this target is appropriate**:
  - *Books to Scrape* is an official open sandbox specifically designed for practicing web scraping techniques without risking disruption to live commercial infrastructure.
- **robots.txt Check Result**:
  - Checking `https://books.toscrape.com/robots.txt` yields a `404 Not Found` response. This means no specific `Disallow` rules exist on the server. However, politeness rules (rate limiting, identification) are still strictly enforced in code.
- **Ethical & Usage Commitment**:
  > *"I will not reuse this code on another site without checking its rules and terms first."*

---

## Quickstart (< 5 minutes)

### Prerequisites
- Python 3.10 or higher installed.

### 1. Installation
```bash
# Clone repository and navigate to directory
cd polite_scrapper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Scraper

Give the website as the first argument:

```bash
# Book mode (auto-detected): books.toscrape.com catalogue
python -m polite_scraper https://books.toscrape.com

# Generic mode: any website (pages metadata: title, h1, headings, links, word counts)
python -m polite_scraper https://quotes.toscrape.com --mode generic --pages 5

# Any URL without a scheme gets https:// added automatically
python -m polite_scraper example.com
```

**CLI options**

| Flag | Description | Default |
|---|---|---|
| `url` | Website to scrape | required |
| `--mode auto\|book\|generic` | `auto` detects book catalogues (via `article.product_pod`) and falls back to generic | `auto` |
| `--pages N` | Max pages to crawl | `3` |
| `--max-links N` | Generic mode: new same-domain links followed per page | `8` |
| `--delay SEC` | Minimum delay between network requests | `0.5` |
| `--timeout SEC` | Request timeout | `10` |
| `--force` | Ignore local HTML cache, re-fetch everything | off |
| `--name NAME` | Custom run folder name (default: derived from the website) | auto |
| `-v, --verbose` | Show per-request logs and raw record checkpoints | off |

**Output files** (in `data/runs/<site-name>/`): `books.json` (book mode), `pages.json` (generic mode), `errors.json`, `run-report.json`. Each run gets its own folder named after the website; if that folder already exists, the run is suffixed (`-1`, `-2`, ...) or renamed via `--name`, so nothing is ever overwritten.

**Polished terminal UI**: progress bars, a run summary table, and an error table are always shown; low-level fetch/cache logs and raw-record checkpoints appear with `-v`.

### 3. Run Tests
```bash
pytest tests/ -v
```

---

## Project Structure

```
polite_scrapper/
├── polite_scraper/          # The scraper package (python -m polite_scraper)
│   ├── main.py              # Entrypoint & pipeline coordinator (CLI)
│   ├── cli.py               # Argument parsing, config mapping & run-folder naming
│   ├── ui.py                # Rich-based terminal UI (progress, tables, panels)
│   ├── config.py            # Centralized settings & simulation hooks
│   ├── fetcher.py           # HTTP client with caching, robots.txt helper & 500ms delay
│   ├── crawler.py           # Catalogue discovery & pagination handler (book mode)
│   ├── generic.py           # Generic site crawler/extractor (any website)
│   ├── extractor.py         # BeautifulSoup HTML detail extractor (book mode)
│   ├── models.py            # Pydantic data schemas (BookRecord, PageRecord)
│   ├── validator.py         # Validation logic & error handler
│   ├── reporter.py          # Output & JSON report generator
│   ├── __main__.py          # python -m polite_scraper entrypoint
│   └── utils.py             # Normalization & URL helper utilities
├── tests/
│   └── test_scraper.py      # Pytest suite
├── data/
│   ├── cache/               # Saved raw HTML files (shared across runs, gitignored)
│   └── runs/                # One output folder per website/run
│       └── <site-name>/     # e.g. books-toscrape-com/
│           ├── books.json   # Validated book records (book mode)
│           ├── pages.json   # Validated page records (generic mode)
│           ├── errors.json  # Validation/fetch errors log
│           └── run-report.json  # Run execution report
├── docs/
│   ├── scraper.md           # This document
│   ├── AI-VS-ME.md          # AI-vs-manual evaluation report
│   └── ai-version/          # Reference AI implementation
├── README.md
├── .gitignore
└── requirements.txt
```

---

## Data Schema

Each record stored in `data/runs/<site-name>/books.json` satisfies the following Pydantic schema (`BookRecord`):

| Field | Type | Description |
|---|---|---|
| `title` | `str` | Non-empty product title |
| `product_url` | `HttpUrl` | Absolute detail page URL |
| `price_text` | `str` | Raw scraped price string (e.g. `"£51.77"`) |
| `price_gbp` | `float` | Normalized float value (e.g. `51.77`) |
| `availability_text` | `str` | Raw stock text (e.g. `"In stock (22 available)"`) |
| `rating_text` | `str` | Raw textual rating (e.g. `"Three"`) |
| `description` | `str \| null` | Clean description text or `null` if absent |
| `source_page` | `HttpUrl` | Catalogue page where discovered |
| `fetched_at` | `str` | ISO-8601 UTC timestamp |

---

## Scraping Workflow

```
[ Classify Target ] ──► [ Fetch Page ] ──► [ Local Cache Check ]
                                                    │
                                                    ▼
[ Generate Report ] ◄── [ Store Output ] ◄── [ Validate Record ] ◄── [ Extract & Normalize ] ◄── [ Discover URLs ]
```

1. **Classify**: Verify target scope and terms.
2. **Fetch**: Perform GET request using identifying `User-Agent` and status checks.
3. **Cache**: Store downloaded HTML in `data/cache/` to make subsequent runs instantaneous and offline-capable.
4. **Discover**: Traverse pagination links on catalogue pages 1 to 3 to extract 60 unique product URLs.
5. **Extract & Normalize**: Parse HTML selectors and derive normalized numeric `price_gbp`.
6. **Validate**: Validate data using Pydantic; divert broken records to `errors.json`.
7. **Store & Report**: Save clean output to the run folder (books.json / pages.json) and performance metrics to run-report.json.

---

## Politeness & Ethics Rules

- **Identifying User-Agent**: Configurable via `USER_AGENT` environment variable; defaults to `PoliteScraper/1.0 (+https://github.com/callmekriztal/polite_scapper)`.
- **robots.txt (generic mode)**: The generic crawler fetches and consults `robots.txt` for every site before crawling and aborts if our User-Agent is disallowed.
- **Request Timeout**: Strict 10-second timeout on all network requests to avoid lingering open sockets.
- **Minimum 500 ms Delay**: Enforced rate limiting (`time.sleep`) between live network HTTP requests. Cached reads execute without artificial sleep.
- **HTTP Status Validation**: Only status `200 OK` is accepted as a successful response.
- **Development Caching**: HTML pages are cached locally during development runs to minimize load on the remote host.
- **No Browser Overhead**: The scraper uses `requests` and `BeautifulSoup4`. Headless browsers (Selenium/Playwright) are not required because the target site serves pre-rendered HTML content directly from the server.

### Ethics Principles
- Always check and respect `robots.txt` and Terms of Service.
- Prefer official APIs when available.
- Never attempt to bypass logins, paywalls, CAPTCHAs, or rate-limit blocks.
- Collect only data necessary for the task scope.

---

## Failure Handling & Broken Page Simulation

The scraper is designed to survive invalid pages or network anomalies without crashing the whole process:
- Any record failing validation or detail page extraction is captured in the run folder errors.json with reason details.
- To test broken page resilience, set the environment variable or config property `BROKEN_TEST_URL`:
  ```bash
  BROKEN_TEST_URL="https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html" python -m polite_scraper https://books.toscrape.com
  ```
  The scraper logs the simulated failure into the run folder errors.json and continues processing all remaining 59 records.

---

## Honest Limitation

- **Static Pagination & Parsing**: The current implementation relies on server-rendered HTML pagination structures (`article.product_pod`, `li.next a`). If the website migrates to dynamic SPA rendering (JavaScript hydration) or updates CSS class schemas, the selectors will require maintenance.

---

## Stage Commit Breakdown Guide

The project implementation is structured across 7 logical commits:

1. **Stage 0**: `git commit -m "feat: classify scraping target and document ethics in README"`
2. **Stage 1**: `git commit -m "feat: implement HTTP fetcher with local HTML caching and politeness delay"`
3. **Stage 2**: `git commit -m "feat: implement catalogue crawler to discover 60 unique book URLs across 3 pages"`
4. **Stage 3**: `git commit -m "feat: implement raw book record extraction using BeautifulSoup selectors"`
5. **Stage 4**: `git commit -m "feat: implement normalization for price_gbp, rating, and string fields"`
6. **Stage 5**: `git commit -m "feat: implement Pydantic validation and broken page error resilience"`
7. **Stage 6**: `git commit -m "feat: implement dataset storage and execution run reporting"`
