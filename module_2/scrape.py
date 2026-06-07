"""
scrape.py — Grad Cafe Web Scraper
----------------------------------
Pulls graduate applicant data from thegradcafe.com using a hybrid
urllib + Selenium + BeautifulSoup workflow.

Workflow:
  1. urllib constructs and validates Grad Cafe URLs.
  2. Selenium renders each page in a headless browser.
  3. BeautifulSoup / regex / string methods parse the rendered HTML.
  4. Raw records are passed to clean.py for structuring.
"""

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.thegradcafe.com"
SEARCH_PATH = "/survey/"

# Polite delay range (seconds) between page requests
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# How many pages to scrape (each page ~20 records; 1,500 pages ~30,000+)
MAX_PAGES = 1500

# Selenium explicit-wait timeout (seconds)
WAIT_TIMEOUT = 15

# How long to pause (seconds) when the site appears to be rate-limiting,
# before rebuilding the browser session and retrying the same page.
RATE_LIMIT_PAUSE = 600  # 10 minutes

# Intermediate file storing raw scraped records for input to clean.py
RAW_FILE = Path("raw_results.json")


# ---------------------------------------------------------------------------
# URL helpers (urllib)
# ---------------------------------------------------------------------------

def _build_search_url(page: int, per_page: int = 20) -> str:
    """
    Construct a Grad Cafe survey URL for the given page number.
    Uses urllib.parse to build the query string safely.
    """
    params = {"page": page, "per_page": per_page}
    query = urllib.parse.urlencode(params)
    return urllib.parse.urljoin(BASE_URL, SEARCH_PATH) + "?" + query


def check_robots_txt() -> bool:
    """
    Fetch and inspect robots.txt. Returns True if /survey/ is allowed
    for a standard browser User-Agent, False otherwise.

    Parsing notes based on the actual thegradcafe.com robots.txt:
    - Several named bots (ClaudeBot, GPTBot, CCBot, AmazonBot, etc.) are
      fully blocked with 'Disallow: /'. These rules apply ONLY to those
      specific User-Agent strings, not to a standard browser UA.
    - The wildcard 'User-agent: *' block disallows only login/account paths
      (/signin, /register, /forgot-password, etc.). /survey/ is not listed,
      so it is permitted for general user-agents.
    - This function checks the wildcard (*) block only, which governs our
      scraper's Mozilla/5.0 browser User-Agent string.
    """
    robots_url = urllib.parse.urljoin(BASE_URL, "/robots.txt")
    print(f"[robots.txt] Fetching: {robots_url}")

    req = urllib.request.Request(robots_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[robots.txt] Could not fetch robots.txt: {exc}")
        return False

    print("[robots.txt] Contents:\n" + "-" * 40)
    print(content)
    print("-" * 40)

    # Parse only the wildcard (*) block — blank line ends each block.
    wildcard_disallowed: list[str] = []
    in_wildcard_block = False

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            in_wildcard_block = False
            continue
        if line.lower().startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            if agent == "*":
                in_wildcard_block = True
            elif in_wildcard_block:
                in_wildcard_block = False
        elif line.lower().startswith("disallow:") and in_wildcard_block:
            path = line.split(":", 1)[1].strip()
            wildcard_disallowed.append(path)

    print(f"[robots.txt] Wildcard (*) Disallow rules: {wildcard_disallowed}")

    for rule in wildcard_disallowed:
        if rule and "/survey/".startswith(rule.rstrip("*")):
            print(f"[robots.txt] /survey/ is DISALLOWED by rule: '{rule}'. Aborting.")
            return False

    print("[robots.txt] /survey/ is ALLOWED. Proceeding with scrape.")
    return True


# ---------------------------------------------------------------------------
# Selenium browser helpers
# ---------------------------------------------------------------------------

def _build_driver() -> webdriver.Chrome:
    """
    Instantiate a headless Chrome WebDriver.
    Uses Selenium Manager (bundled with Selenium 4.6+) to handle
    ChromeDriver automatically — no manual driver download required.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def _get_page_source(driver: webdriver.Chrome, url: str, retries: int = 3) -> str | None:
    """
    Navigate to url with Selenium, wait for the page body to load,
    and return the fully rendered page source. Returns None on failure.

    Retries up to `retries` times on timeout with an increasing wait
    between attempts. A timeout may indicate a transient network issue
    rather than a deliberate block. If all attempts fail, returns None
    and the caller decides whether to skip or stop.
    """
    for attempt in range(1, retries + 2):
        try:
            print(f"[Selenium] Attempt {attempt}/{retries + 1}: navigating to {url}")
            driver.get(url)
            # Wait for body — works regardless of exact HTML structure
            print(f"[Selenium] Waiting for page body...")
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Short pause to let JS-rendered content settle
            time.sleep(2)
            source = driver.page_source
            print(f"[Selenium] Loaded: {driver.title!r} ({len(source):,} chars)")
            return source
        except Exception as exc:
            print(f"[Selenium] Attempt {attempt}/{retries + 1} failed for {url}: {exc}")
            if attempt <= retries:
                wait = 10 * attempt  # 10s then 20s before retrying
                print(f"[Selenium] Waiting {wait}s before retry...")
                time.sleep(wait)
    return None


def _parse_entry(summary_row, detail_row) -> dict:
    """
    Extract a single applicant record from a pair of <tr> tags.

    GradCafe renders each result as TWO consecutive rows:
      summary_row  — 4 columns: School | Program+DegreeType | Added On | Decision+URL
      detail_row   — 1 wide column containing:
                       • A tags/stats line:  "Accepted on May 15   Fall 2026   International   GPA 3.84"
                       • (optionally) a free-text comment paragraph below it

    All required fields map as follows:
      raw_institution_program  ← summary col 0  (school name)
      raw_degree_status        ← summary col 1  (program name + degree type concatenated)
      raw_date                 ← summary col 2  (date added to GradCafe, e.g. "May 29, 2026")
      raw_decision             ← summary col 3  (short decision label, e.g. "Accepted on May 15")
      url                      ← <a href> in summary col 3
      raw_tags                 ← first text block in detail row
                                 contains: decision date · semester/year · student type ·
                                           GPA · GRE Q · GRE V · GRE AW
      raw_notes                ← free-text comment in detail row (everything after the tags line)
    """
    # ---- summary row -------------------------------------------------------
    cells = summary_row.find_all("td")
    if len(cells) < 3:
        return {}

    raw_institution_program = cells[0].get_text(separator=" ", strip=True)

    # Col 1 merges program name and degree type, e.g. "Consumer ScienceMasters"
    raw_degree_status = cells[1].get_text(separator=" ", strip=True) if len(cells) > 1 else ""

    # Col 2: date entry was added to GradCafe ("May 29, 2026")
    raw_date = cells[2].get_text(separator=" ", strip=True) if len(cells) > 2 else ""

    # Col 3: short decision label + link
    decision_cell = cells[3] if len(cells) > 3 else None
    raw_decision = decision_cell.get_text(separator=" ", strip=True) if decision_cell else ""

    # URL to individual result page.
    # Search the entire summary row for any /result/ link — the anchor can
    # appear on the school name, the decision text, or elsewhere depending
    # on GradCafe's current markup.
    url = ""
    for a_tag in summary_row.find_all("a", href=True):
        href = a_tag["href"]
        if "/result/" in href:
            url = href if href.startswith("http") else urllib.parse.urljoin(BASE_URL, href)
            break

    # ---- detail row --------------------------------------------------------
    # The detail row holds structured tag tokens AND the free-text comment.
    # Both live in the same <td>. The tag tokens match known patterns:
    #   season   — "Fall 2026", "Spring 2025", etc.
    #   status   — "American", "International"
    #   GPA      — "GPA 3.84"
    #   GRE      — "GRE 320", "GRE V 165", "GRE AW 4.0"
    #   decision — "Accepted on May 15", "Rejected on Jun 02"
    # Everything that does NOT match any tag pattern is free-text notes.
    _TAG_RE = re.compile(
        r"^("
        r"(fall|spring|summer|winter)\s+\d{4}"           # season
        r"|american|international|domestic"               # student type
        r"|gpa\s*[\d.]+"                                  # GPA token
        r"|gre(\s+(v(erbal)?|q(uant)?|aw|writing))?\s*[\d.]+"  # GRE token
        r"|(accepted|rejected|waitlisted|interview\w*)"   # decision word
        r"(\s+on\s+.*)?"                                  # optional "on <date>"
        r")$",
        re.I,
    )

    raw_tags = ""
    raw_notes = ""

    if detail_row is not None:
        detail_td = detail_row.find("td")
        if detail_td:
            # Gather all text from the cell, splitting on whitespace runs of 3+
            # chars OR newlines — these are the natural token boundaries GradCafe uses.
            full_text = detail_td.get_text(separator="\n", strip=True)
            all_tokens = [
                t.strip()
                for t in re.split(r"\n+|\s{3,}", full_text)
                if t.strip()
            ]

            tag_tokens, note_tokens = [], []
            for token in all_tokens:
                if _TAG_RE.match(token):
                    tag_tokens.append(token)
                else:
                    note_tokens.append(token)

            raw_tags  = "   ".join(tag_tokens)
            raw_notes = " ".join(note_tokens).strip()

    # Merge decision label + tags into a single string that clean.py can mine
    # for: decision date, semester, student type, GPA, GRE scores.
    raw_degree_status_full = " | ".join(
        filter(None, [raw_degree_status, raw_decision, raw_tags])
    )

    return {
        "raw_institution_program": raw_institution_program,
        "raw_degree_status":       raw_degree_status_full,
        "raw_date":                raw_date,
        "raw_notes":               raw_notes,
        "url":                     url,
    }


def _parse_page(html: str) -> list[dict]:
    """
    Parse all applicant rows from a rendered Grad Cafe HTML page.

    GradCafe's survey table alternates between summary rows and detail rows.
    The page contains a single <table>; rows come in pairs:
      odd  → summary  (School / Program / Added On / Decision)
      even → detail   (tags line + free-text comment)

    Strategy:
      1. Locate the results table (any <table> containing result links).
      2. Collect all <tr> children, skipping the header.
      3. Walk pairs: (summary_row, detail_row) → _parse_entry().
    """
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []

    # Find the table that contains result links (/result/ paths)
    result_table = None
    for table in soup.find_all("table"):
        if table.find("a", href=re.compile(r"/result/", re.I)):
            result_table = table
            break

    # Fallback: any table on the page
    if result_table is None:
        result_table = soup.find("table")

    if result_table is None:
        return records

    # Collect all <tr> rows, skip the header row (first <tr> or <thead> rows)
    all_rows = result_table.find_all("tr")

    # Drop header rows (those that contain <th> elements)
    data_rows = [r for r in all_rows if not r.find("th")]

    # Walk in pairs: summary row followed immediately by its detail row
    i = 0
    while i < len(data_rows):
        summary = data_rows[i]

        # A summary row has ≥3 <td> cells and a result link
        is_summary = (
            len(summary.find_all("td")) >= 3
            and summary.find("a", href=re.compile(r"/result/", re.I))
        )

        if is_summary:
            # The very next row is the detail row (may or may not exist)
            detail = data_rows[i + 1] if (i + 1) < len(data_rows) else None

            # Confirm the next row is actually a detail row (few or 1 <td>)
            if detail is not None and len(detail.find_all("td")) >= 3:
                # Next row looks like another summary — no detail row present
                detail = None
            else:
                i += 1  # consume the detail row

            entry = _parse_entry(summary, detail)
            if entry:
                records.append(entry)

        i += 1

    return records


# ---------------------------------------------------------------------------
# Resume helper
# ---------------------------------------------------------------------------

def _get_resume_page(output_file: Path) -> int:
    """
    Read raw_results.json and return the next page to scrape based on
    the '_resume_from_page' marker written on failure. If no marker exists
    and no file exists, returns 1.
    """
    if not output_file.exists():
        return 1
    try:
        with open(output_file, encoding="utf-8") as fh:
            data = json.load(fh)
        # Check for resume marker (written on failure/stop)
        if isinstance(data, dict) and "_resume_from_page" in data:
            resume = data["_resume_from_page"]
            print(f"[scrape] Resume marker found. Resuming from page {resume}.")
            return resume
        # Fallback: infer from records
        if isinstance(data, list) and data:
            last_page = max(r.get("source_page", 0) for r in data)
            resume = last_page + 1
            print(f"[scrape] Found {len(data):,} existing records. "
                  f"Resuming from page {resume}.")
            return resume
        return 1
    except Exception as exc:
        print(f"[scrape] Could not read {output_file}: {exc}. Starting from page 1.")
        return 1


def _write_resume_marker(records: list[dict], next_page: int, path: Path) -> None:
    """
    Save records plus a '_resume_from_page' marker so the next run
    knows where to continue. The marker is removed once scraping completes
    successfully via _save_raw (which writes a clean list with no marker).
    """
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"_resume_from_page": next_page, "records": records},
                  fh, ensure_ascii=False, indent=2)


def _load_existing_records(output_file: Path) -> list[dict]:
    """Load existing records from raw_results.json, handling both
    plain list format and the resume-marker dict format."""
    if not output_file.exists():
        return []
    try:
        with open(output_file, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "records" in data:
            return data["records"]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_data(max_pages: int = MAX_PAGES, output_file: Path = RAW_FILE, start_page: int = 1) -> None:
    """
    Main scraping entry point.

    1. Checks robots.txt.
    2. Builds paginated Grad Cafe URLs with urllib.
    3. Renders each page with Selenium.
    4. Parses each page with BeautifulSoup / regex / string methods.
    5. Returns a list of raw applicant record dicts.

    Args:
        max_pages:   Maximum number of survey pages to scrape.
        output_file: Path to save raw records (default: raw_results.json).
        start_page:  Page to start from. Use this to resume a previous run.
    """
    if not check_robots_txt():
        raise RuntimeError("robots.txt disallows scraping /survey/. Aborting.")

    # Load any existing records from a previous run
    all_records: list[dict] = _load_existing_records(output_file)
    if all_records:
        print(f"[scrape] Loaded {len(all_records):,} existing records.")
    driver = _build_driver()

    try:
        page_num = start_page
        while page_num <= max_pages:
            url = _build_search_url(page=page_num)
            print(f"[scrape] Page {page_num}: {url}")

            # Polite delay between requests (skip on first page)
            if page_num > start_page:
                delay = MIN_DELAY + (MAX_DELAY - MIN_DELAY) * (page_num % 7) / 6
                time.sleep(delay)

            html = _get_page_source(driver, url)

            # ---- Rate-limit / load failure: pause then rebuild session ----
            if html is None or not _parse_page(html):
                reason = (
                    "failed to load after all retries"
                    if html is None
                    else "page loaded but returned no records — site may be blocking"
                )
                print(f"[scrape] Page {page_num}: {reason}.")

                # Save progress so data is safe during the pause.
                _write_resume_marker(all_records, page_num, output_file)
                print(f"[scrape] {len(all_records):,} records saved. "
                      f"Pausing {RATE_LIMIT_PAUSE // 60} minutes before retrying "
                      f"page {page_num} with a fresh browser session...")

                # Tear down the poisoned session before sleeping.
                try:
                    driver.quit()
                except Exception:
                    pass

                # Count down so the console shows the scrape is still alive.
                remaining = RATE_LIMIT_PAUSE
                while remaining > 0:
                    print(f"[scrape] Resuming in {remaining // 60}m {remaining % 60:02d}s…",
                          end="\r", flush=True)
                    time.sleep(min(30, remaining))
                    remaining -= min(30, remaining)
                print()  # newline after the countdown

                # Rebuild the driver and retry the same page — do NOT advance.
                driver = _build_driver()
                print(f"[scrape] Fresh browser session ready. Retrying page {page_num}.")
                continue  # retry the same page_num

            # ---- Successful page ----
            records = _parse_page(html)
            for r in records:
                r["source_page"] = page_num
                r["source_url"] = url
            all_records.extend(records)
            print(f"[scrape] Page {page_num}: {len(records)} records "
                  f"(total: {len(all_records):,})")

            # Incremental checkpoint every 50 pages
            if page_num % 50 == 0:
                _save_raw(all_records, output_file)
                print(f"[scrape] Checkpoint saved ({len(all_records):,} records).")

            page_num += 1  # only advance on success

    finally:
        driver.quit()

    _save_raw(all_records, output_file)
    print(f"[scrape] Done. {len(all_records):,} raw records saved to {output_file}.")


def _save_raw(records: list[dict], path: Path) -> None:
    """Persist raw records to a JSON file (incremental checkpoint).
    Writes a clean list with no resume marker — call this on success."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    # Automatically resumes from where the last run stopped.
    # Optionally pass a page number to override: python scrape.py 101
    start = int(sys.argv[1]) if len(sys.argv) > 1 else _get_resume_page(RAW_FILE)
    scrape_data(start_page=start)