"""
app.py
------
Flask web application that:
  - Displays Grad Café query results on a dynamic webpage
  - Provides a "Pull Data" button to trigger Module 2 scraping
  - Provides an "Update Analysis" button to refresh query results
"""

import threading

import psycopg2
from psycopg2 import extras
from flask import Flask, jsonify, render_template

from query_data import get_all_results
from db_config import get_connection
from load_data import compute_row_hash, parse_float, parse_date, INSERT_SQL
from scrape import scrape_data
from clean import clean_data

app = Flask(__name__)


class _ScrapeState:
    """Thread-safe flag tracking whether a scrape is currently running."""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False

    def try_start(self) -> bool:
        """Mark scraping as running. Returns False if already running."""
        with self._lock:
            if self._running:
                return False
            self._running = True
            return True

    def finish(self) -> None:
        """Mark scraping as finished."""
        with self._lock:
            self._running = False

    @property
    def running(self) -> bool:
        """Whether a scrape is currently in progress."""
        with self._lock:
            return self._running


_scrape_state = _ScrapeState()


def _build_row(record: dict) -> tuple:
    """Convert one cleaned scrape record into an applicants-table row tuple,
    including its row_hash for dedup."""
    fields = {
        "program": record.get("program"),
        "comments": record.get("comments"),
        "date_added": parse_date(record.get("date_added")),
        "status": record.get("status"),
        "term": record.get("term"),
        "gpa": parse_float(record.get("GPA")),
        "gre": parse_float(record.get("GRE")),
        "gre_v": parse_float(record.get("GRE V")),
        "gre_aw": parse_float(record.get("GRE AW")),
        "degree": record.get("Degree"),
    }
    row_hash = compute_row_hash(fields)

    return (
        fields["program"], fields["comments"], fields["date_added"],
        record.get("url"), fields["status"], fields["term"],
        record.get("US/International"), fields["gpa"], fields["gre"],
        fields["gre_v"], fields["gre_aw"], fields["degree"],
        record.get("llm-generated-program"), record.get("llm-generated-university"),
        row_hash,
    )


def _insert_rows(rows: list) -> None:
    """Insert applicant rows into the database, skipping duplicates by row_hash."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            extras.execute_values(cur, INSERT_SQL, rows, page_size=500)
        conn.commit()
    finally:
        conn.close()


def _run_scraper():
    """
    Background thread: scrape → clean → insert into DB, all in memory.
    raw_results.json is still written by scrape_data() as a checkpoint,
    but applicant_data.json is never created — cleaned records go straight
    into the database via psycopg2.
    """
    try:
        # Step 1: Scrape (output_file=None means no file written, records returned in memory)
        raw_records = scrape_data(max_pages=10, output_file=None, start_page=1)

        # Step 2: Clean in memory
        cleaned = clean_data(raw_records)

        # Step 3: Insert directly into DB, reusing load_data.py's row-hash
        # dedup so this stays in sync with the load path and doesn't rely
        # on `url` uniqueness alone.
        rows = [_build_row(record) for record in cleaned]
        _insert_rows(rows)

        print(f"✓ Scrape, clean, and load completed. {len(rows)} records processed.")

    except (OSError, ValueError, RuntimeError, ImportError, psycopg2.Error) as e:
        print(f"Scraper/load error: {e}")
    finally:
        _scrape_state.finish()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Render the main analysis page."""
    return render_template("index.html")


@app.route("/api/results")
def api_results():
    """Return all query results as JSON (called by Update Analysis button)."""
    try:
        data = get_all_results()
        return jsonify({"status": "ok", "data": data})
    except psycopg2.Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/pull_data", methods=["POST"])
def api_pull_data():
    """
    Trigger the Module 2 scraper to pull new data.
    Returns 409 if scraping is already running.
    """
    if not _scrape_state.try_start():
        return jsonify({
            "status": "running",
            "message": "A data pull is already in progress. Please wait."
        }), 409

    thread = threading.Thread(target=_run_scraper, daemon=True)
    thread.start()

    return jsonify({
        "status": "started",
        "message": "Data pull started! This may take several minutes. "
                   "Use 'Update Analysis' when it completes."
    })


@app.route("/api/scrape_status")
def api_scrape_status():
    """Return whether a scrape is currently running."""
    return jsonify({"running": _scrape_state.running})


if __name__ == "__main__":
    app.run(host="localhost", port=8080)
