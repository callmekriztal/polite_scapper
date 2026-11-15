<div align="center">

# 🕷️ The Polite Scraper

**A rate-limited, cache-first web scraper with a polished terminal UI — that treats every host with respect.**

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-10%20passing-brightgreen)](tests/)
[![Modes](https://img.shields.io/badge/modes-book%20%7C%20generic-blueviolet)](#two-modes)
[![UI](https://img.shields.io/badge/ui-rich%20terminal-FF69B4)](https://github.com/Textualize/rich)
[![Ethics](https://img.shields.io/badge/robots.txt-checked-success)](#%EF%B8%8F-politeness--ethics)

</div>

---

The Polite Scraper crawls websites the way a good citizen would: it identifies itself with a custom User-Agent, waits at least 500 ms between live requests, caches every page it downloads so re-runs cost the server **nothing**, validates everything it extracts against strict [Pydantic](https://docs.pydantic.dev/) schemas, and survives broken pages without crashing.

Give it a URL — it figures out the rest.

```bash
python -m polite_scraper https://books.toscrape.com
```

```
╭───────────────────────────── The Polite Scraper ─────────────────────────────╮
│ Target      https://books.toscrape.com/                                      │
│ Mode        book                                                             │
│ Run folder  data/runs/books-toscrape-com                                     │
│ Max pages   3                                                                │
│ Min delay   0.5s between requests                                            │
│ Cache       data/cache                                                       │
╰───────── polite by design — rate-limited, cached, identify-yourself ─────────╯

───────────────────────── Discovering catalogue pages ──────────────────────────
  ✓ 3 catalogue pages crawled — 60 unique book URLs

───────────────────── Extracting & validating book details ─────────────────────
  ✓ 60 valid books, 0 rejected

───────────────────────────────────── Done ─────────────────────────────────────
╭──────────────────────────────── Run Summary ─────────────────────────────────╮
│      Requests  0 network / 64 cache                                          │
│ Records saved  60                                                            │
│      Duration  0.772s                                                        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## ✨ Features

| | |
|---|---|
| 🎯 **One command, any site** | Pass the website as a plain argument — no config files, no code changes |
| 🧠 **Auto mode detection** | Probes the target and picks the right extractor automatically |
| 💾 **Disk cache** | Every fetched page is stored locally — second runs are instant and offline |
| 🐢 **Rate limiting** | Hard 500 ms minimum delay between live HTTP requests (configurable) |
| 🪪 **Identifiable** | Custom `User-Agent` sent with every request |
| 🤖 **robots.txt aware** | Generic mode consults `robots.txt` before crawling and aborts if disallowed |
| ✅ **Strict validation** | Pydantic schemas reject malformed records into `errors.json` instead of crashing |
| 🧱 **Resilient** | A broken page fails alone — the run continues and reports it |
| 📊 **Full reporting** | `run-report.json` with duration, cache hits, network fetches and record counts |
| 🖥️ **Clean terminal UI** | Progress bars, summary tables and panels via [`rich`](https://github.com/Textualize/rich) — quiet by default, `-v` for full logs |

## 📦 Two Modes

### `book` — catalogue scraper
Built for e-commerce-style catalogues (originally [books.toscrape.com](https://books.toscrape.com/)). Follows pagination (`li.next a`), discovers product links, then extracts per-product: **title, price (raw + normalized), availability (raw + structured), rating, description, source page, timestamp**.

### `generic` — any website
BFS-crawls same-domain links (rate-limited, robots.txt-checked) and extracts per-page metadata: **title, h1, meta description, headings, same-domain links, image count, word count**.

### `auto` — the default
Fetches the seed page and checks for book-catalogue markup (`article.product_pod`). Book catalogue → book mode. Anything else → generic mode.

## 🚀 Quickstart

```bash
git clone https://github.com/callmekriztal/polite_scapper.git
cd polite_scapper

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

```bash
# Book catalogue (auto-detected)
python -m polite_scraper https://books.toscrape.com

# Any other website, deeper crawl
python -m polite_scraper https://quotes.toscrape.com --mode generic --pages 5

# Bare domains get https:// added automatically
python -m polite_scraper example.com
```

Every run gets **its own output folder**, named after the website:

```
data/runs/
├── books-toscrape-com/     ← books.toscrape.com run
├── quotes-toscrape-com/    ← quotes.toscrape.com run
└── my-domain-org-2/        ← third run on my-domain.org (auto-suffixed)
```

If a folder for that website already exists, you'll be asked to pick a new name — or just press Enter to accept an auto-suffix (`-1`, `-2`, …) so no run ever overwrites another. Override the name with `--name my-custom-run`.

## ⌨️ CLI Reference

```
usage: polite-scraper [-h] [--mode {auto,book,generic}] [--pages PAGES]
                      [--max-links MAX_LINKS] [--delay DELAY]
                      [--timeout TIMEOUT] [--force] [-v] [url]
```

| Flag | Description | Default |
|---|---|---|
| `url` | Website to scrape (required) | — |
| `--mode auto\|book\|generic` | Scraper mode | `auto` |
| `--pages N` | Maximum pages to crawl | `3` |
| `--max-links N` | Generic mode: new same-domain links followed per page | `8` |
| `--delay SEC` | Minimum delay between live requests | `0.5` |
| `--timeout SEC` | Request timeout | `10` |
| `--force` | Ignore the local cache, re-fetch everything | off |
| `--name NAME` | Custom run folder name (default: derived from the website) | auto |
| `-v, --verbose` | Show per-request logs and raw record checkpoints | off |

Environment variables still work for `USER_AGENT`, `TIMEOUT`, `MIN_DELAY_SECONDS` and `BROKEN_TEST_URL` — CLI flags win when both are set.

## 📁 Output

Every run writes into its own folder under `data/runs/`:

| File | Mode | Contents |
|---|---|---|
| `books.json` | book | Validated product records |
| `pages.json` | generic | Validated page-metadata records |
| `errors.json` | both | Validation / fetch failures with reasons |
| `run-report.json` | both | Full execution metrics |

<details>
<summary>Example record — <code>books.json</code></summary>

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
<summary>Example record — <code>pages.json</code> (generic mode)</summary>

```json
{
  "url": "https://quotes.toscrape.com/",
  "title": "Quotes to Scrape",
  "h1": "Quotes to Scrape",
  "meta_description": null,
  "headings": ["Quotes to Scrape", "Top Ten tags"],
  "same_domain_links": ["https://quotes.toscrape.com/login", "..."],
  "link_count": 47,
  "image_count": 0,
  "word_count": 282,
  "fetched_at": "2026-11-15T08:44:55.123456+00:00"
}
```
</details>

## 🏗️ Architecture

```
                    ┌─────────────┐
   CLI argument ──► │  cli.py     │  argparse → Config
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  fetcher.py │  session · UA · rate limit · disk cache · robots.txt
                    └──────┬──────┘
             ┌─────────────┴─────────────┐
             ▼                           ▼
     ┌──────────────┐            ┌──────────────┐
     │  crawler.py  │            │  generic.py  │
     │  (book mode) │            │ (any website)│
     └──────┬───────┘            └──────┬───────┘
             ▼                           ▼
     ┌──────────────┐            ┌──────────────┐
     │ extractor.py │            │  BFS links   │
     └──────┬───────┘            └──────┬───────┘
             └───────────┬───────────────┘
                         ▼
                 ┌───────────────┐
                 │ validator.py  │  Pydantic: BookRecord / PageRecord
                 └───────┬───────┘
                         ▼
                 ┌───────────────┐
                 │  reporter.py  │  books.json · pages.json · errors.json · run-report.json
                 └───────────────┘
```

Each stage is isolated — swapping the extractor or the target site never touches the fetch, validation, or reporting layers.

## 🧪 Testing

```bash
pytest tests/ -v
```

Covers price/rating/availability normalization, Pydantic validation failures, broken-page simulation, generic extraction, and CLI config mapping.

## 🤝 Politeness & Ethics

- **Identifying `User-Agent`** on every request (configurable via `USER_AGENT`)
- **Minimum 500 ms delay** between live network requests — cache reads never sleep
- **`robots.txt` consulted** in generic mode; the run aborts if our agent is disallowed
- **Only `200 OK` accepted** — no retries that hammer a struggling server
- **Caching by default** so development re-runs cost the target server zero requests

> *I will not reuse this code on another site without checking its rules and terms first.*

## 📚 More Documentation

The deep-dive — stage-by-stage design decisions, data schema tables, failure-handling hooks, and the internship assignment context — lives in **[`docs/scraper.md`](docs/scraper.md)****.
