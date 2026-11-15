# 03 — Technical Concepts

Every concept below is *used by this codebase*. For each: first principles, how it works, where it appears (file + line), why it's useful here, a minimal example, and likely interview questions.

## 1. HTTP requests and response handling

**First principles.** HTTP is a request/response protocol: the client sends method + path + headers (+ optional body); the server returns a status code (2xx success, 3xx redirect, 4xx client error, 5xx server error), headers, and a body. A GET fetches a representation of a resource.

**How it works here.** `fetcher.py` uses a `requests.Session` (line 16) — an object that pools TCP connections (keep-alive) so successive requests to the same host skip the TCP/TLS handshake, and that carries default headers (the `User-Agent`, line 17–19). Status policy is strict: any status ≠ 200 raises `requests.HTTPError` (lines 84–89). `response.encoding = "utf-8"` (line 81) pins the text decoding.

**Why here.** A polite crawler must identify itself (UA), reuse connections (fewer handshakes = less server load), and treat unexpected statuses as failures rather than parsing garbage.

**Example.**
```python
session = requests.Session()
session.headers["User-Agent"] = "PoliteScraper/1.0 (+contact)"
r = session.get("https://books.toscrape.com/", timeout=10)
r.encoding = "utf-8"          # before touching r.text
if r.status_code != 200:
    raise requests.HTTPError(f"{r.status_code}", response=r)
```

**Interview angles:** why a Session?; why set `.encoding` before `.text`?; what does `timeout=10` bound (the whole exchange, not per-phase)?; what status codes would you accept besides 200?

## 2. Rate limiting (politeness delay)

**First principles.** A rate limiter caps how often an action may occur. Simplest form: minimum interval between events. More advanced: token buckets, sliding windows.

**How it works here.** `fetcher.py` `_network_get` (69–75): before each *live* request, compute `elapsed = now - last_request_time`; if below `MIN_DELAY_SECONDS`, `time.sleep(diff)`. The limiter is instance-level state — because `main.run` creates exactly one `Fetcher`, the limit is **global** across crawler, extractor, and generic scraper. Cache reads bypass it entirely (`fetch()` returns before `_network_get`), so warm runs never sleep.

**Why here.** The project's whole identity: scraping without hammering the host. 500 ms ⇒ max ~2 requests/second.

**Example.**
```python
now = time.monotonic()
elapsed = now - self.last_request_time
if elapsed < 0.5:
    time.sleep(0.5 - elapsed)
self.last_request_time = now
```

**Interview angles:** cache reads skip the delay — is that OK? (yes: zero server load); single-threaded assumption (the limiter is not thread-safe); robots.txt fetch bypasses it — named gap (fetcher.py 57).

## 3. Disk caching of fetched pages

**First principles.** A cache stores computed/fetched results keyed by input; a *cache hit* serves the stored copy. Determinism matters: same key ⇒ same file.

**How it works here.** `fetcher.fetch` (24–48): `url_to_cache_filename(url)` (utils.py 19–36) builds the key — regex branches for toscrape catalogue pages, slug+MD5 for details, full MD5 for anything else. Existing file → read, count `cache_hits`, return `(html, True)`. Miss → network → `write_text` (line 47). `--force` (`FETCH refresh`, config.FORCE_REFRESH, line 30) skips reads but still re-writes.

**Why here.** Re-runs (development, demos, tests) cost the host **zero** requests; HTML is cached rather than parsed data so extractor changes don't invalidate the cache.

**Example.**
```python
key = f"detail-{hashlib.md5(url.encode()).hexdigest()}.html"
path = cache_dir / key
if path.is_file() and not force:
    return path.read_text(encoding="utf-8"), True
html = network_get(url)
path.write_text(html, encoding="utf-8")
return html, False
```

**Interview angles:** why cache HTML not JSON? (schema evolves independently); MD5 collisions (practically impossible at this scale); cache invalidation (none — `--force` is the manual invalidator); TOCTOU between `is_file()` and `read_text` (guarded by the except at 43).

## 4. Web crawling vs. scraping; BFS

**First principles.** Crawling = traversing links to discover pages (graph traversal). Scraping = extracting structured data from a page. A scraper alone hits one URL; a crawler explores.

**How it works here.** Book mode *crawls* pagination (`crawler.py` 25–53: follow `li.next a` linearly — a linked-list traversal) then *scrapes* detail pages (`extractor.py`). Generic mode BFS-crawls the link graph: `deque.popleft()` (generic.py 119) = FIFO = breadth-first; frontier growth bounded by `--max-links`; global budget `--pages`.

**Why here.** BFS with a page budget approximates "most navigationally important pages first" and gives deterministic, reproducible crawls.

**Example.**
```python
queue, seen = deque([start]), {start}
while queue and fetched < max_pages:
    url = queue.popleft()
    html = fetch(url)
    for link in extract_links(html):
        if link not in seen:
            seen.add(link); queue.append(link)
```

**Interview angles:** why deque not list (`pop(0)` is O(n), `popleft()` is O(1))?; why same-domain only (unbounded web crawl otherwise)?; complexity (O(pages × links-per-page)).

## 5. URL parsing, normalization, joining

**First principles.** URLs decompose into scheme://netloc/path?query#fragment. Joining resolves a relative reference against a base per RFC 3986. Normalization makes equivalent URLs textually equal.

**How it works here.** `utils.make_absolute_url` = `urljoin` (utils.py 15–17) used on every discovered link. Generic mode normalizes by stripping fragments (`split("#")[0]`, generic.py 59/115) and comparing `netloc` (58). CLI normalizes the input: scheme default + trailing slash (cli.py 106–110). Cache keys are the strongest normalization: full URL → MD5 (utils.py 32–35).

**Why here.** Deduplication and correctness: `about` vs `/about` vs `../about` must resolve to one absolute URL or the crawler double-visits pages.

**Interview angles:** what does `urljoin("https://x.com/a/b.html", "../c")` give? (`https://x.com/c`); why fragments stripped (in-page anchors are the same document); scheme/host case handling (not done — a known limitation).

## 6. HTML parsing and CSS selectors

**First principles.** HTML is a tree; a parser builds a DOM-like object model. CSS selectors address nodes by tag/class/id/structure.

**How it works here.** BeautifulSoup with the stdlib `"html.parser"` everywhere. Selectors used: `article.product_pod`, `h3 a`, `li.next a` (crawler.py 33–48); `div.product_main`, `p.price_color`, `p.instock.availability`, `p.star-rating`, `#product_description` (extractor.py 34–62); `find_all(HEADING_TAGS)`, `find("meta", attrs={"name": "description"})`, `find_all("a", href=True)`, `find_all("img")` (generic.py 34–76). Class-based data (the star rating) is read from `tag.get("class", [])` (extractor.py 55). `decompose()` removes nodes from the tree (generic.py 64).

**Why here.** The sandbox sites are server-rendered; a headless browser would be pure overhead (stated in `docs/scraper.md`).

**Interview angles:** `select` vs `find`/`select_one` (CSS syntax vs method args); why `html.parser` (no C deps, adequate speed); what happens on malformed HTML (BS4 is forgiving; parsers diverge on edge cases).

## 7. Python packages, `-m`, and `__name__ == "__main__"`

Covered in depth in [04_execution_and_entry_points.md](04_execution_and_entry_points.md). Summary: `__init__.py` makes a directory importable; `__main__.py` makes it executable with `-m`; the `__name__` guard distinguishes execution from import (`__main__.py` line 3, `main.py` line 223).

## 8. Dataclasses and Pydantic models

**First principles.** Both reduce boilerplate for data objects. `@dataclass` generates `__init__`/`__repr__`/`__eq__` — structure without behavior. Pydantic models additionally *validate and coerce at runtime*, with typed serialization.

**How it works here — both are used, deliberately.**
- `Config` (`config.py` @dataclass): settings, mutated at runtime; per-field `default_factory` for cwd-relative paths (17–21); env defaults evaluated at class-definition time (7–12).
- `RunMetrics` (`reporter.py` @dataclass): serialized with `dataclasses.asdict` (66).
- `BookRecord`/`PageRecord` (`models.py` Pydantic): runtime contracts — `Field(ge=0.0)`, `min_length=1`, `HttpUrl`, `field_validator` with `@classmethod`, `from e` exception chaining (models.py 23–30).

**Why both.** Metrics/config need shape, not validation (they're internally produced). Scraped records need runtime validation (external, untrusted data). Using Pydantic for config would be ceremony; using dataclasses for records would lose the schema gate.

**Example.**
```python
@dataclass
class Metrics:
    duration: float

class BookRecord(BaseModel):
    price: float = Field(ge=0)
BookRecord(price=-1)   # → ValidationError
```

**Interview angles:** when dataclass vs Pydantic; `default_factory` vs mutable default (the classic `=[]` trap — `headings` uses `default_factory=list`, models.py 39); what `model_dump(mode="json")` does.

## 9. Type hints

**First principles.** Annotations document and enable static checking; the interpreter ignores them at runtime (except some tooling).

**How it works here.** Signatures throughout: `fetch(self, url: str, force_refresh: bool = False) -> tuple[str, bool]` (fetcher.py 24); modern union syntax `str | None` (config.py 32, validator.py via `BookRecord | None`); `tuple[list, list, dict]` returns in main.py (53, 113); `dict[str, Any]` (validator.py). Deliberately loose spots: `model: type` in `validator._validate` (line 21) — could be `type[BaseModel]`; `list` without parameters in main.py returns.

**Why here.** IDE support and self-documenting data shapes (e.g. `tuple[str, bool]` tells you `fetch` returns a pair immediately).

**Interview angles:** are hints enforced? (no, runtime-ignored — Pydantic is the runtime layer); `X | None` vs `Optional[X]` (identical semantics, 3.10+ syntax); why `Any` appears in the error-dict shapes.

## 10. Exception handling

**First principles.** Exceptions unwind the call stack until a matching `except`. Precise catches localize failure; broad catches convert crashes into recovery.

**How it works here.** A layered policy:
- **Precise**: `except requests.RequestException` (fetcher.py 58, main.py 44), `except ValidationError` (validator.py 33), `except KeyboardInterrupt` (main.py 218).
- **Broad as isolation**: per-item `except Exception` around each extraction (main.py 98) and each generic fetch (generic.py 123) — one bad page fails alone.
- **Swallow-and-degrade**: cache read errors (fetcher.py 43).
- **Errors as data**: validator converts `ValidationError` into a dict (33–47).
- **Chaining**: `raise ... from e` in models.py 29–30 — preserves the original traceback context.

**What is NOT caught** (verified): book-mode discovery failures (crawler → main: crash); filesystem errors in reporter; `SystemExit` is deliberately not caught (it *is* an exception — the robots-abort and probe-failure paths rely on it propagating).

**Interview angles:** `except Exception` vs `except BaseException` (the latter would catch KeyboardInterrupt/SystemExit); EAFP vs LBYL (this codebase is mostly LBYL checks + EAFP boundaries); exception chaining value.

## 11. CLI development with argparse

Covered in [modules/cli.md](modules/cli.md). Core facts: `argparse.ArgumentParser` subclass overriding `error()` for friendly failures (cli.py 22–28); `nargs="?"` + post-parse requirement check; `choices` for `--mode`; `action="version"`; `RawDescriptionHelpFormatter` for the epilog. Interview angle: why not click/typer? (zero-dependency CLI; stdlib argparse is sufficient for 10 options).

## 12. Configuration management

Layered defaults: env vars (read at import, config.py 7–12) → dataclass defaults → CLI overrides (cli.py 102–125) → runtime mutation (`OUTPUT_DIR`, `START_URL` in main.py 147/153). Precedence fact: CLI flags beat env for numeric settings; env beats the default UA string. Interview angle: why mutate a config object instead of passing parameters? (single mutable state object mirrors the single `Fetcher`).

## 13. File handling

UTF-8 everywhere: cache writes/reads `encoding="utf-8"` (fetcher.py 38/47), JSON writes `encoding="utf-8"` + `ensure_ascii=False` (reporter.py 39–40, 55–56). `mkdir(parents=True, exist_ok=True)` for idempotent directory creation (config.py 38–40). Paths via `pathlib.Path` (`/` operator composition). **No atomic writes** (no tmp+rename) — a crash mid-write leaves truncated JSON (see [08_improvements_and_roadmap.md](08_improvements_and_roadmap.md)).

## 14. Data validation

Schema-at-the-boundary pattern: extractors return dicts → `RecordValidator` enforces the Pydantic contract → validated models → `model_dump(mode="json")` for storage. Bad records become error dicts with the raw payload preserved (validator.py 34–39) — the audit-trail pattern. Interview angle: why validate after extraction rather than during? (parsing stays total; the gate is one chokepoint).

## 15. robots.txt and crawling etiquette

**First principles.** robots.txt (RFC 9309) is a per-site file declaring rules per user-agent: `Disallow`/`Allow` path prefixes. Etiquette beyond robots: identify yourself, throttle, cache, don't circumvent.

**How it works here.** `Fetcher.fetch_robots_txt` (fetcher.py 50–67) fetches and parses with stdlib `RobotFileParser`. `GenericSiteScraper.check_robots` (generic.py 91–103) checks the *seed* URL (abort on denial); `_robots_allows` (150–153) filters *every* enqueued link. Absent robots.txt (404) → "no rules" → proceed. Identified UA string is the same one sent as the HTTP header — rules match the actual requests.

**Why here.** It is the difference between a scraper and a polite scraper — and it only exists in generic mode (book mode skips it; books.toscrape.com has no robots.txt anyway, verified 404).

**Interview angles:** 404 vs 5xx semantics (this code treats both as "no rules" — RFC leans conservative on 5xx); `can_fetch` matching (prefix rules, `*` wildcards, longest-match); why book mode doesn't check (assignment scope, target known-safe sandbox).

## 16. Retry mechanisms — explicitly absent

Fact: there are **no retries anywhere**. A failed fetch raises, the caller quarantines it. Justification to give in an interview: the politeness policy treats failures as data; blind retries against a struggling server are the opposite of polite. A production-grade version would add bounded backoff for 5xx/timeouts only.
