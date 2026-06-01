# Module 2 — Grad Cafe Web Scraper

## 1. Name

Saishrithik Sareddy — 9A9D11

---

## 2. Module Info

- **Module:** Module 2
- **Assignment:** Web Scraping & Data Cleaning — Grad Cafe Applicant Data
- **Due Date:** 05/31/2026

---

## 3. Approach

### Scraping (`scrape.py`)

The scraper uses a hybrid urllib + Selenium + BeautifulSoup workflow.

First, `check_robots_txt()` fetches `https://www.thegradcafe.com/robots.txt`
using `urllib.request` and parses the wildcard (`*`) block for any `Disallow`
rules covering `/survey/`. If `/survey/` is disallowed the script aborts
immediately. Based on the actual robots.txt, only login/account paths are
disallowed for general user-agents — `/survey/` is not listed, so scraping
is permitted. A screenshot of the robots.txt is included as `screenshot.jpg`.

`_build_search_url()` uses `urllib.parse` to construct paginated URLs in the
form `https://www.thegradcafe.com/survey/?page=N&per_page=25`.

For each page, `_get_page_source()` uses Selenium with a headless Chrome
browser to fully render the page (Grad Cafe loads results via JavaScript, so
a plain urllib request does not return applicant rows). An explicit wait for
the page `body` element is used before extracting `page_source`.

**Browser/Driver:** Google Chrome (headless) + ChromeDriver, managed
automatically by Selenium Manager (bundled in Selenium ≥ 4.6). No manual
driver download is required.

`_parse_page()` passes the rendered HTML to BeautifulSoup to locate the
results table. `_parse_entry()` then extracts each row's cells using
BeautifulSoup's `find_all()` and `get_text()`, capturing:

- Cell 0: raw institution and program name
- Cell 1: degree type and applicant status (includes acceptance/rejection date)
- Cell 2: date the entry was added to Grad Cafe
- Cell 3: applicant notes containing GPA, GRE scores, comments, student type
- Anchor tag href: URL link to the individual applicant entry

Polite behavior is maintained with a 2–4 second variable delay between page
requests plus a 2 second wait for JS content to settle. The scraper stops
immediately if a page returns no records, which may indicate rate-limiting.

### Cleaning (`clean.py`)

`scrape_data()` saves raw records to `raw_results.json` as an intermediate file.
`clean_data()` reads from `raw_results.json`, iterates over the records, and
calls `_clean_record()` on each one. All extraction uses Python string methods
and `re` (regex) — no external services.

- `_split_institution_program()` splits the combined institution/program string
  on common separators (`-`, `–`, `|`) into separate university and program fields
- `_normalize_status()` maps keywords to `Accepted / Rejected / Waitlisted / Interview`
- `_normalize_degree()` maps keywords to `PhD / Masters`
- `_extract_gpa()` uses regex patterns like `GPA: 3.75` and `3.85/4.0`
- `_extract_gre()` extracts GRE Verbal, Quant, and AW scores via regex
- `_extract_date()` handles multiple date formats and converts to ISO-8601
- `_extract_student_type()` detects `American / International` from keywords
- `_extract_semester_year()` extracts terms like `Fall 2024` via regex
- `_strip_html()` removes residual HTML tags and entities from all text fields

Raw scraped text is preserved alongside cleaned fields in every record for
traceability. Missing values are represented as `null`.

`save_data()` writes the cleaned records to `applicant_data.json` as valid JSON.

### Resume Mechanism (`scrape.py`)

If the scraper encounters any failure — timeout, 500 error, or rate-limiting —
it immediately stops, writes a `_resume_from_page` marker into `raw_results.json`
along with all records collected so far, and exits cleanly. Stopping immediately
ensures Selenium objects are fully torn down and recreated fresh on the next run.

Running `python scrape.py` again with no arguments automatically detects the
marker, loads the existing records, and resumes from the page where it stopped.
No manual intervention or arguments are needed.

Once scraping completes successfully, `_save_raw()` writes a clean JSON array
with no marker so the file is ready for `clean.py`.

### LLM Standardization (`llm_hosting/app.py`)

The provided starter code was incorporated as-is and debugged for Python 3.10+
compatibility (`str | None` union hints replaced with `Optional[str]` from
`typing`). The `_cli_process_file()` function was parallelized using
`concurrent.futures.ThreadPoolExecutor` with a `--workers` flag defaulting to
CPU count. LLM inference calls are serialised via `_LLM_INFER_LOCK` since
`llama.cpp` is not reentrant. A `write_lock` ensures thread-safe JSONL output.

Running `python app.py --file ../applicant_data.json --stdout` passes each
record's `program` field through TinyLlama 1.1B (local, no API key required)
which proposes standardized `llm-generated-program` and `llm-generated-university`
values. These are then post-processed through abbreviation expansion, typo fixes,
title-case normalization, canonical list matching, and fuzzy matching via `difflib`.

---

## 4. Known Bugs / Edge Cases

- The `program` field on Grad Cafe frequently mixes program and university names
  in a single string with inconsistent separators. The regex splitter handles
  common cases but may not split correctly for all entries. The `llm_hosting`
  standardizer addresses this more robustly.
- GRE scores are absent for many recent applicants as programs have dropped the
  GRE requirement. These fields will be `null` for those records.
- Acceptance and rejection dates are embedded within the status text field rather
  than in a dedicated field. They are extracted via the regex date parser, which
  may miss unusual date formats.
- Some entries display GPA, semester, and student type as HTML tags in a
  sub-row or extra cells below the main result row (e.g. `Fall 2026`,
  `International`, `GPA 3.40`). The fixed `_parse_entry()` captures these by
  reading extra cells and the next sibling row and appending them to `raw_notes`.
  Entries scraped before this fix will have `null` for these fields.
- Occasional read timeouts occur when Grad Cafe rate-limits requests. The scraper
  retries each failed page up to 2 times with a 10-20 second wait between attempts.
  If all retries fail the page is skipped and scraping continues. If many consecutive
  pages fail, the scraper stops as required by the assignment.