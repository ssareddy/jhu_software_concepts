"""
app.py
------
Flask web application that:
  - Displays Grad Café query results on a dynamic webpage
  - Provides a "Pull Data" button to trigger Module 2 scraping
  - Provides an "Update Analysis" button to refresh query results
"""

import os
import threading
import subprocess
import sys
from flask import Flask, jsonify, render_template

# Import query helpers from query_data.py
from query_data import get_all_results

app = Flask(__name__)

# Thread-safe flag to track if scraping is currently running
_scrape_lock = threading.Lock()
_scrape_running = False


def _run_scraper():
    """
    Background thread: scrape → clean → insert into DB, all in memory.
    raw_results.json is still written by scrape_data() as a checkpoint,
    but applicant_data.json is never created — cleaned records go straight
    into the database via psycopg2.
    """
    global _scrape_running
    try:
        import psycopg2
        from psycopg2 import extras
        from pathlib import Path

        module_dir = os.path.abspath(os.path.dirname(__file__))

        # Step 1: Scrape (output_file=None means no file written, records returned in memory)
        sys.path.insert(0, module_dir)
        from scrape import scrape_data
        raw_records = scrape_data(max_pages=10, output_file=None, start_page=1)

        # Step 2: Clean in memory
        from clean import clean_data
        cleaned = clean_data(raw_records)

        # Step 4: Insert directly into DB, skipping duplicates via url UNIQUE
        from query_data import DB_CONFIG
        conn = psycopg2.connect(**DB_CONFIG)

        def parse_float(val):
            try:
                return float(val) if val not in (None, "", "N/A") else None
            except (ValueError, TypeError):
                return None

        rows = []
        for r in cleaned:
            rows.append((
                r.get("program"),
                r.get("comments"),
                r.get("date_added"),
                r.get("url"),
                r.get("status"),
                r.get("term"),
                r.get("US/International"),
                parse_float(r.get("GPA")),
                parse_float(r.get("GRE")),
                parse_float(r.get("GRE V")),
                parse_float(r.get("GRE AW")),
                r.get("Degree"),
                r.get("llm-generated-program"),
                r.get("llm-generated-university"),
            ))

        INSERT_SQL = """
            INSERT INTO applicants (
                program, comments, date_added, url, status, term,
                us_or_international, gpa, gre, gre_v, gre_aw, degree,
                llm_generated_program, llm_generated_university
            ) VALUES %s
            ON CONFLICT (url) DO NOTHING;
        """
        with conn.cursor() as cur:
            extras.execute_values(cur, INSERT_SQL, rows, page_size=500)
        conn.commit()
        conn.close()

        print(f"✓ Scrape, clean, and load completed. {len(rows)} records processed.")

    except Exception as e:
        print(f"Scraper/load error: {e}")
    finally:
        with _scrape_lock:
            _scrape_running = False


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
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/pull_data", methods=["POST"])
def api_pull_data():
    """
    Trigger the Module 2 scraper to pull new data.
    Returns 409 if scraping is already running.
    """
    global _scrape_running
    with _scrape_lock:
        if _scrape_running:
            return jsonify({
                "status": "running",
                "message": "A data pull is already in progress. Please wait."
            }), 409
        _scrape_running = True

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
    return jsonify({"running": _scrape_running})


if __name__ == "__main__":
    app.run(host="localhost", port=8080)