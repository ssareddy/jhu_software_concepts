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

`_parse_page()` passes the rendered HTML to BeautifulSoup and locates the
results table by finding a `<table>` that contains `/result/` links. Each
result on the Grad Cafe survey page is rendered as **two consecutive `<tr>`
rows**:

- **Summary row** — 4 columns: School name | Program + Degree type | Date
  added to GradCafe | Decision label + link to individual result page
- **Detail row** — 1 wide column containing two logical blocks:
  1. A structured tags line: `"Accepted on May 15   Fall 2026   International   GPA 3.84"`
     (space-separated tokens for decision date, semester, student type, GPA, GRE scores)
  2. The applicant's free-text comment (everything below the tags line)

`_parse_page()` walks all non-header `<tr>` elements in pairs, identifying
summary rows by the presence of a `/result/` href. `_parse_entry()` takes the
summary and detail row as a pair and populates:

- `raw_institution_program` — school name (summary col 0)
- `raw_degree_status` — program + degree type + decision label + tags line,
  pipe-joined so downstream extractors can mine all structured fields from one string
- `raw_date` — date the entry was added to GradCafe (summary col 2)
- `raw_notes` — free-text applicant comment (detail row, block 2)
- `url` — absolute URL to the individual result page

Polite behavior is maintained with a 2–4 second variable delay between page
requests plus a 2 second wait for JS content to settle. The scraper retries
each failed page up to 2 times (10 s then 20 s between attempts) and stops if
a page returns no records, which may indicate rate-limiting.

### Cleaning (`clean.py`)

`scrape_data()` saves raw records to `raw_results.json`. `clean_data()` reads
that file and calls `_clean_record()` on each record. All extraction uses Python
string methods and `re` (regex) — no external services.

**University / Program extraction:**

- `raw_institution_program` (col 0) is the school name only — assigned directly
  to `university`.
- The program name is extracted from the first pipe-segment of `raw_degree_status`
  (the raw col-1 text), with degree-type keywords (`PhD`, `Masters`, `MBA`, …)
  stripped from the end via regex, leaving just the program name.

**Other extractors:**

- `_normalize_status()` — maps keywords to `Accepted / Rejected / Waitlisted / Interview`
- `_normalize_degree()` — maps keywords to `PhD / Masters`
- `_extract_decision_date()` — searches `raw_notes` first for a status-keyed date
  phrase (e.g. `"Accepted on Apr 17"`); falls back to parsing `raw_date` only if
  none is found. When a note date has no year, the year is borrowed from `raw_date`
  rather than the current date, since the post date is always ≥ the decision date.
- `_extract_date()` — parses `raw_date` into ISO-8601 for the `date_added` field
- `_extract_gpa()` — regex patterns: `GPA: 3.75`, `3.85/4.0`, `4.00 GPA`
- `_extract_gre()` — extracts GRE Verbal, Quant, AW; computes total from V+Q
- `_extract_student_type()` — detects `American / International` from keywords
- `_extract_semester_year()` — extracts terms like `Fall 2024` via regex
- `_strip_html()` — removes residual HTML tags and entities from all text fields
- `comments` — the full `raw_notes` text, set to `null` only if the notes contain
  nothing beyond a bare status word (e.g. `"Accepted"`)

Raw scraped text is preserved alongside cleaned fields in every record for
traceability. Missing values are represented as `null`.

`save_data()` writes cleaned records to `applicant_data.json` as a valid JSON array.

### Resume Mechanism (`scrape.py`)

If the scraper encounters any failure — timeout, 500 error, or rate-limiting —
it writes a `_resume_from_page` marker into `raw_results.json` along with all
records collected so far, and exits cleanly. Running `python scrape.py` again
automatically detects the marker, loads the existing records, and resumes from
the page where it stopped.

Once scraping completes successfully, `_save_raw()` writes a clean JSON array
with no marker so the file is ready for `clean.py`.

### LLM Standardization (`llm_hosting/app.py`)

Each record's `program` field is passed through TinyLlama 1.1B (local, no API
key required) which proposes standardized `llm-generated-program` and
`llm-generated-university` values. These are post-processed through abbreviation
expansion, typo fixes, title-case normalization, canonical list matching, and
fuzzy matching via `difflib`.

The CLI (`--file` mode) processes all records and writes a single valid JSON
array to the output file (default: `llm_extend_applicant_data.json`). The HTTP
server mode (`--serve`) exposes a `/standardize` endpoint accepting
`{"rows": [...]}` and returning `{"rows": [...]}` with the two LLM fields added.

---

## 4. How to Run

### Prerequisites

Install all dependencies:

```bash
pip install -r requirements.txt
```

Google Chrome must be installed for Selenium. ChromeDriver is managed
automatically by Selenium Manager — no manual download required.

### Step 1 — Scrape

```bash
python incremental_scraper.py
```

Scrapes up to 1,500 pages (~30,000 records) from GradCafe and writes raw
records to `raw_results.json`. If interrupted, re-run the same command to
resume automatically from where it stopped.

To start from a specific page:

```bash
python incremental_scraper.py 101
```

### Step 2 — Clean

```bash
python clean.py
```

Reads `raw_results.json`, extracts and structures all fields, and writes
`applicant_data.json`.

### Step 3 — LLM Standardization

```bash
python llm_hosting/app.py --file applicant_data.json --out llm_extend_applicant_data.json
```

Reads `applicant_data.json`, runs each record's `program` field through the
local TinyLlama model, and writes `llm_extend_applicant_data.json` as a valid
JSON array with `llm-generated-program` and `llm-generated-university` fields
added to every record.

To run the HTTP server instead:

```bash
python llm_hosting/app.py --serve
# POST {"rows": [...]} to http://localhost:8000/standardize
```

---

## 5. Output Files

| File | Description |
|---|---|
| `raw_results.json` | Raw scraped records (output of `scrape.py`) |
| `applicant_data.json` | Cleaned, structured records (output of `clean.py`) |
| `llm_extend_applicant_data.json` | LLM-augmented records with standardized program/university names |

---

## 6. Known Bugs / Edge Cases

- GRE scores are absent for many recent applicants as programs have dropped the
  GRE requirement. These fields will be `null` for those records.
- Some decision date notes omit the year (e.g. `"Accepted on Apr 17"`). The
  year is inferred from `raw_date` (the post date), which is always ≥ the actual
  decision date. This is correct for the vast majority of cases; an entry posted
  in January for a December decision would be off by one year.
- GradCafe occasionally restructures its HTML. If `_parse_page()` returns zero
  records on pages that visually show results, inspect the rendered HTML for
  table structure changes.
- Occasional read timeouts occur when GradCafe rate-limits requests. The scraper
  retries each failed page up to 2 times with 10–20 second waits. If all retries
  fail the resume marker is written and the script exits cleanly.