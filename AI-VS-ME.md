# AI-VS-ME Evaluation Report

Comparison template evaluating the AI-generated implementation (`ai-version/`) against hand-built implementation checkpoints for the FlyRank Internship W5 A9 "The Polite Scraper" assignment.

---

## Evaluation Checkpoints

| Checkpoint | Status | AI Implementation Result |
|---|---|---|
| **3 Catalogue Pages** | PASSED | Crawled `page-1.html`, `page-2.html`, `page-3.html` dynamically via BeautifulSoup `li.next a` selector. |
| **60 Unique Book URLs** | PASSED | Discovered exactly 60 unique book detail URLs without duplicates across 3 pages. |
| **60 Validated Records** | PASSED | All 60 records validated successfully against Pydantic schema (`BookRecord`). |
| **Rerun Without Duplicate Records** | PASSED | Subsequent runs produce identical 60 records without duplication or extra fetches. |
| **Caching** | PASSED | Local HTML file caching in `cache/`; 2nd run resulted in 63 cache hits and 0 network requests in 1.39s. |
| **500 ms Minimum Delay** | PASSED | Enforced minimum 0.5s pause between live HTTP requests; 0s sleep for cache reads. |
| **User-Agent** | PASSED | Configurable User-Agent: `FlyRankInternshipA9/1.0 (+https://github.com/YOUR_USERNAME/YOUR_REPO)`. |
| **Timeout** | PASSED | Explicit 10-second timeout on all GET requests. |
| **Validation** | PASSED | Pydantic model (`BookRecord`) checking non-empty title, numeric non-negative float `price_gbp`, and valid ISO-8601 timestamps. |
| **Broken-Page Survival** | PASSED | `BROKEN_TEST_URL` simulation hook catches errors per page, appends error context to `output/errors.json`, and allows the scraper to finish remaining records. |
| **Run Report** | PASSED | Generates `output/run-report.json` with duration, cache hits, network fetches, and exact record counts. |

---

## Detailed Feedback & Analysis

### 1. What the AI Implementation Did Better
- **Automated ISO-8601 UTC Timestamping & UTF-8 Encoding**: Explicitly set `response.encoding = 'utf-8'` to prevent character corruption (`Â£51.77` -> `£51.77`).
- **Comprehensive Pydantic Schema**: Strong schema enforcement with custom field validators for ISO-8601 datetime verification and title non-emptiness.
- **Detailed Run Metrics**: Tracks precise execution duration, network fetch counts vs cache hits, broken page counts, and outputs cleanly formatted JSON reports.

### 2. What the AI Implementation Got Wrong or Silently Skipped Initially
- **Cache Key Overlap Bug**: Initial regex matching for URL cache filename matched all detail URLs ending in `index.html` to `catalogue-page-1.html`, causing detail pages to load catalogue HTML. This was identified and fixed by refining `url_to_cache_filename` to differentiate catalogue page 1 from detail page URLs.

### 3. What My Original Prompt Forgot to Specify
- **HTTP Response Text Encoding**: Did not explicitly mandate setting `response.encoding = 'utf-8'` on `requests.Response`, which can lead `requests` to default to `ISO-8859-1` on standard headers.
- **Cache File Naming Convention for Detail Pages**: Required `cache/catalogue-page-1.html` for catalogue page 1, but left detail page cache naming unspecified, requiring deterministic slug + hash mapping.

### 4. Concrete Differences Between Implementations
1. **Cache Resolution Logic**: AI uses a deterministic URL hashing strategy (`detail-<slug>-<md5_hash[:8]>.html`) for product detail pages while reserving standard human-readable filenames for catalogue pages (`catalogue-page-1.html`).
2. **Error Resilience Architecture**: Rather than wrapping the entire scraping loop in a `try...except`, AI wraps per-item extraction calls in isolated exception blocks, feeding failures to `RecordValidator` and logging them directly to `output/errors.json`.
3. **Simulation Hook**: Provides `BROKEN_TEST_URL` environment variable support to test broken detail page handling predictably without making broken live HTTP network requests.

### 5. What Changed After Improving the Prompt
- Added explicit instructions for UTF-8 character encoding handling for British Pound currency symbols (`£`).
- Clarified the requirement for explicit Pydantic v2 `BookRecord` model validation.
