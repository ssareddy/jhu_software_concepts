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
    """Run the Module 2 scraper in a background thread."""
    global _scrape_running
    try:
        # Adjust the path to your Module 2 scraper as needed
        scraper_path = os.path.join(
            os.path.dirname(__file__), "..", "module_2", "scraper.py"
        )
        subprocess.run(
            [sys.executable, scraper_path],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        print(f"Scraper error: {e}")
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
