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
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
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


def check_robots_txt() -> bool:  # pragma: no cover
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
    except RuntimeError as exc:
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

def _build_driver() -> ChromeDriver:  # pragma: no cover
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
    return ChromeDriver(options=options)


def _get_page_source(  # pragma: no cover
    driver: ChromeDriver, url: str, retries: int = 3
) -> str | None:
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
            print("[Selenium] Waiting for page body...")
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Short pause to let JS-rendered content settle
            time.sleep(2)
            source = driver.page_source
            print(f"[Selenium] Loaded: {driver.title!r} ({len(source):,} chars)")
            return source
        except RuntimeError as exc:
            print(f"[Selenium] Attempt {attempt}/{retries + 1} failed for {url}: {exc}")
            if attempt <= retries:
                wait = 10 * attempt  # 10s then 20s before retrying
                print(f"[Selenium] Waiting {wait}s before retry...")
                time.sleep(wait)
    return None


def _safe_quit(driver: ChromeDriver, timeout: int = 8) -> None:  # pragma: no cover
    """
    Quit the Selenium driver without risking a hang.

    driver.quit() can block indefinitely when Chrome is already in a bad
    state (rate-limited, network stalled, crashed). This helper runs quit()
    in a daemon thread so it cannot freeze the main process:
      - If quit() finishes within `timeout` seconds — clean exit.
      - If it times out, the thread is abandoned, and we fall back to
        force-killing the chromedriver subprocess via its PID.
    """
    import threading  # pylint: disable=import-outside-toplevel
    import signal    # pylint: disable=import-outside-toplevel
    import os as _os  # pylint: disable=import-outside-toplevel

    def _quit():
        try:
            driver.quit()
        except RuntimeError:
            pass

    t = threading.Thread(target=_quit, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        print(f"\n[scrape] driver.quit() hung after {timeout}s — force-killing Chrome.")
        try:
            pid = driver.service.process.pid
            # SIGKILL forcefully terminates the process on Unix/Linux/macOS.
            # SIGILL is used on Windows where SIGKILL is not available.
            kill_signal = (
                signal.SIGKILL  # pylint: disable=no-member
                if hasattr(signal, "SIGKILL")
                else signal.SIGILL
            )
            _os.kill(pid, kill_signal)
        except RuntimeError:
            pass


def _extract_url(summary_row) -> str:
    """Find and return the GradCafe result URL from the row."""
    for a_tag in summary_row.find_all("a", href=True):
        href = a_tag["href"]
        if "/result/" in href:
            return href if href.startswith("http") else urllib.parse.urljoin(BASE_URL, href)
    return ""


def _parse_entry(summary_row, tags_row, notes_row) -> dict:
    """Extract a single applicant record from consecutive <tr> tags."""
    cells = summary_row.find_all("td")
    if len(cells) < 3:
        return {}

    # Extract decision, tags, and notes directly without extra assignments
    raw_decision = ""
    if len(cells) > 3:
        full_text = cells[3].get_text(separator=" ", strip=True)
        m = re.search(
            r"(accepted|rejected|waitlisted|wait\s*listed|interview\w*)"
            r"(\s+on\s+[A-Za-z]+\s+\d{1,2}(?:,?\s*\d{4})?)?",
            full_text, re.I,
        )
        raw_decision = m.group(0).strip() if m else full_text

    if tags_row and tags_row.find("td"):
        raw_tags = tags_row.find("td").get_text(separator="   ", strip=True)
    else:
        raw_tags = ""

    if notes_row and notes_row.find("td"):
        raw_notes = notes_row.find("td").get_text(separator=" ", strip=True)
    else:
        raw_notes = ""

    return {
        "raw_institution_program": cells[0].get_text(separator=" ", strip=True),
        "raw_degree_status": " | ".join(
            filter(None, [
                cells[1].get_text(separator=" ", strip=True) if len(cells) > 1 else "",
                raw_decision,
                raw_tags
            ])
        ),
        "raw_date": cells[2].get_text(separator=" ", strip=True) if len(cells) > 2 else "",
        "raw_notes": raw_notes,
        "url": _extract_url(summary_row),
    }


def _parse_page(html: str) -> list[dict]:
    """
    Parse all applicant rows from a rendered Grad Cafe HTML page.

    GradCafe renders each result as THREE consecutive <tr> rows:
      Row 0 (5 cells) — summary: School | Program | DegreeType | Added On | Decision
      Row 1 (1 cell)  — tags:    "Rejected on Jun 02   Fall 2026   American"
      Row 2 (1 cell)  — notes:   free-text applicant comment (may be absent)

    Strategy:
      1. Find the results table (contains /result/ links).
      2. Drop header rows (those with <th>).
      3. Walk rows: identify summary rows by cell count (≥3) + /result/ link.
         Consume the next 1-2 single-cell rows as tags and notes respectively.
    """
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []

    # Find the table containing result links
    result_table = None
    for table in soup.find_all("table"):
        if table.find("a", href=re.compile(r"/result/", re.I)):
            result_table = table
            break
    if result_table is None:
        result_table = soup.find("table")
    if result_table is None:
        return records

    # Drop header rows
    data_rows = [r for r in result_table.find_all("tr") if not r.find("th")]

    i = 0
    while i < len(data_rows):
        row = data_rows[i]
        n_cells = len(row.find_all("td"))
        is_summary = (
            n_cells >= 3
            and row.find("a", href=re.compile(r"/result/", re.I))
        )

        if not is_summary:
            i += 1
            continue

        # Peek at the next two rows to find tags and notes rows.
        # A tags/notes row has exactly 1 <td> and no /result/ link.
        def _is_detail(r):
            return (
                r is not None
                and len(r.find_all("td")) == 1
                and not r.find("a", href=re.compile(r"/result/", re.I))
            )

        tags_row = (
            data_rows[i + 1]
            if (i + 1) < len(data_rows) and _is_detail(data_rows[i + 1])
            else None
        )
        notes_row = (
            data_rows[i + 2]
            if (i + 2) < len(data_rows) and _is_detail(data_rows[i + 2])
            else None
        )

        # Only consume rows that are actually detail rows
        consumed = 1
        if tags_row is not None:
            consumed += 1
        if notes_row is not None:
            consumed += 1

        entry = _parse_entry(row, tags_row, notes_row)
        if entry:
            records.append(entry)

        i += consumed

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
    except RuntimeError as exc:
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
    if output_file is None or not output_file.exists():
        return []
    try:
        with open(output_file, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "records" in data:
            return data["records"]
    except RuntimeError:
        pass
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_data(  # pragma: no cover
    max_pages: int = MAX_PAGES, output_file: Path = RAW_FILE, start_page: int = 1
) -> list:
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
                if output_file is not None:
                    _write_resume_marker(all_records, page_num, output_file)
                print(f"[scrape] {len(all_records):,} records saved. "
                      f"Pausing {RATE_LIMIT_PAUSE // 60} minutes before retrying "
                      f"page {page_num} with a fresh browser session...")

                # Tear down the poisoned session before sleeping.
                # Use _safe_quit so a hanging Chrome can't block the countdown.
                _safe_quit(driver)

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

            # Incremental checkpoint every 50 pages (only if saving to file)
            if output_file is not None and page_num % 50 == 0:
                _save_raw(all_records, output_file)
                print(f"[scrape] Checkpoint saved ({len(all_records):,} records).")

            page_num += 1  # only advance on success

    finally:
        _safe_quit(driver)

    # Only save to file when output_file is provided (CLI runs).
    # When called from app.py with output_file=None, return records in memory
    # to avoid bloating raw_results.json on every Pull Data request.
    if output_file is not None:
        _save_raw(all_records, output_file)
        print(f"[scrape] Done. {len(all_records):,} raw records saved to {output_file}.")
    else:
        print(f"[scrape] Done. {len(all_records):,} raw records returned in memory.")

    return all_records


def _save_raw(records: list[dict], path: Path) -> None:
    """Persist raw records to a JSON file (incremental checkpoint).
    Writes a clean list with no resume marker — call this on success."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import sys

    # Automatically resumes from where the last run stopped.
    # Optionally pass a page number to override: python scrape.py 101
    start = int(sys.argv[1]) if len(sys.argv) > 1 else _get_resume_page(RAW_FILE)
    scrape_data(start_page=start)
