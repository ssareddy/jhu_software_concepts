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
    """Run the Module 2 scraper in a background thread, then load new data into DB."""
    global _scrape_running
    try:
        module_dir = os.path.abspath(os.path.dirname(__file__))
        raw_json_path     = os.path.join(module_dir, "raw_results.json")
        cleaned_json_path = os.path.join(module_dir, "applicant_data.json")

        # Step 1: Import and run scrape_data (first 10 pages only)
        # New entries appear at the top of Grad Café so this captures recent data.
        # ON CONFLICT DO NOTHING in load_data.py handles any duplicates.
        sys.path.insert(0, module_dir)
        from scrape import scrape_data
        from pathlib import Path
        scrape_data(max_pages=10, output_file=Path(raw_json_path), start_page=1)

        # Step 2: Clean the raw records using clean.py
        import json
        from clean import clean_data, save_data
        with open(raw_json_path, encoding="utf-8") as f:
            raw_records = json.load(f)
        # Handle resume-marker format
        if isinstance(raw_records, dict) and "records" in raw_records:
            raw_records = raw_records["records"]
        cleaned = clean_data(raw_records)
        save_data(cleaned, Path(cleaned_json_path))

        # Step 3: Load cleaned data into the database
        load_data_path = os.path.join(module_dir, "load_data.py")
        subprocess.run(
            [sys.executable, load_data_path, "--json", cleaned_json_path],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✓ Scrape, clean, and load completed successfully.")

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
    app.run(debug=True, host="0.0.0.0", port=5000)