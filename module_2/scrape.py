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
MIN_DELAY = 2.0
MAX_DELAY = 4.0

# How many pages to scrape (each page ~20 records; 1,500 pages ~30,000+)
MAX_PAGES = 1500

# Selenium explicit-wait timeout (seconds)
WAIT_TIMEOUT = 15

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


def _get_page_source(driver: webdriver.Chrome, url: str, retries: int = 2) -> str | None:
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
            driver.get(url)
            # Wait for body — works regardless of exact HTML structure
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


# ---------------------------------------------------------------------------
# HTML parsing helpers (BeautifulSoup + regex + string methods)
# ---------------------------------------------------------------------------

def _parse_entry(row) -> dict:
    """
    Extract a single applicant record from a <tr> BeautifulSoup Tag.
    Captures all fields required by the assignment. Returns a dict of
    raw (unparsed) field strings for downstream cleaning in clean.py.

    Required fields captured here:
      - Program Name / University  → raw_institution_program
      - Comments                   → raw_notes
      - Date Added to Grad Cafe    → raw_date
      - URL link to entry          → url
      - Applicant Status           → raw_degree_status
      - Acceptance / Rejection Date (within raw_degree_status)
      - Semester / Year            (within raw_institution_program / raw_notes)
      - International / American   (within raw_notes)
      - GRE, GRE V, GPA, GRE AW   (within raw_notes)
      - Masters or PhD             (within raw_degree_status)
    """
    cells = row.find_all("td")
    if len(cells) < 4:
        return {}

    # Cell 0: institution and program name
    raw_institution_program = cells[0].get_text(separator=" ", strip=True)

    # Cell 1: degree type and applicant status (includes acceptance/rejection date)
    raw_degree_status = cells[1].get_text(separator=" ", strip=True) if len(cells) > 1 else ""

    # Cell 2: date the entry was added to Grad Cafe
    raw_date = cells[2].get_text(separator=" ", strip=True) if len(cells) > 2 else ""

    # Cell 3: applicant notes — contains GPA, GRE scores, comments,
    #         student type (International/American), semester/year
    raw_notes = cells[3].get_text(separator=" ", strip=True) if len(cells) > 3 else ""

    # URL link to the individual applicant entry
    link_tag = row.find("a", href=True)
    url = ""
    if link_tag:
        href = link_tag["href"]
        url = href if href.startswith("http") else urllib.parse.urljoin(BASE_URL, href)

    return {
        "raw_institution_program": raw_institution_program,
        "raw_degree_status":       raw_degree_status,
        "raw_date":                raw_date,
        "raw_notes":               raw_notes,
        "url":                     url,
    }


def _parse_page(html: str) -> list[dict]:
    """
    Parse all applicant rows from a rendered Grad Cafe HTML page.
    Uses BeautifulSoup for DOM traversal plus string/regex fallbacks.
    """
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []

    # Primary: find a results table
    result_table = soup.find("table", class_=re.compile(r"results|survey", re.I))
    if not result_table:
        result_table = soup.find("table")

    if result_table:
        rows = result_table.find_all("tr", class_=re.compile(r"^r[01]$|row", re.I))
        if not rows:
            rows = result_table.find_all("tr")[1:]  # skip header row
        for row in rows:
            entry = _parse_entry(row)
            if entry:
                records.append(entry)

    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_data(max_pages: int = MAX_PAGES, output_file: Path = RAW_FILE) -> list[dict]:
    """
    Main scraping entry point.

    1. Checks robots.txt.
    2. Builds paginated Grad Cafe URLs with urllib.
    3. Renders each page with Selenium.
    4. Parses each page with BeautifulSoup / regex / string methods.
    5. Returns a list of raw applicant record dicts.
    """
    if not check_robots_txt():
        raise RuntimeError("robots.txt disallows scraping /survey/. Aborting.")

    all_records: list[dict] = []
    driver = _build_driver()

    try:
        for page_num in range(1, max_pages + 1):
            url = _build_search_url(page=page_num)
            print(f"[scrape] Page {page_num}: {url}")

            # Polite delay between requests (skip on first page)
            if page_num > 1:
                delay = MIN_DELAY + (MAX_DELAY - MIN_DELAY) * (page_num % 7) / 6
                time.sleep(delay)

            html = _get_page_source(driver, url)
            if html is None:
                print(f"[scrape] Page {page_num}: failed to load. Skipping.")
                continue

            records = _parse_page(html)
            if not records:
                print(f"[scrape] Page {page_num}: no records found — "
                      "site may be blocking. Stopping early.")
                break

            for r in records:
                r["source_page"] = page_num
                r["source_url"] = url
            all_records.extend(records)
            print(f"[scrape] Page {page_num}: {len(records)} records "
                  f"(total: {len(all_records):,})")

            # Incremental save every 50 pages
            if page_num % 50 == 0:
                _save_raw(all_records, output_file)
                print(f"[scrape] Checkpoint saved ({len(all_records):,} records).")

    finally:
        driver.quit()

    _save_raw(all_records, output_file)
    print(f"[scrape] Done. {len(all_records):,} raw records saved to {output_file}.")
    return all_records


def _save_raw(records: list[dict], path: Path) -> None:
    """Persist raw records to a JSON file (incremental checkpoint)."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    scrape_data()