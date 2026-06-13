"""
app.py
------
Flask web application that:
  - Displays Grad Café query results on a dynamic webpage
  - Provides a "Pull Data" button to trigger scraping
  - Provides an "Update Analysis" button to refresh query results

Exposes a create_app() factory for testability.
DATABASE_URL env var overrides DB_CONFIG when set.
"""

import os
import threading
from flask import Flask, jsonify, render_template

# ---------------------------------------------------------------------------
# Thread-safe busy state (module-level so tests can reset it)
# ---------------------------------------------------------------------------
_scrape_lock = threading.Lock()
_scrape_running = False


def _set_busy(val: bool) -> None:
    global _scrape_running
    with _scrape_lock:
        _scrape_running = val


def is_busy() -> bool:
    return _scrape_running


def create_app(scraper_fn=None, loader_fn=None, query_fn=None):
    """
    Application factory.

    Parameters
    ----------
    scraper_fn : callable | None
        Injected scraper. If None, the real scrape_data is imported lazily.
    loader_fn  : callable | None
        Injected loader (scrape → clean → insert pipeline). If None, the
        real _run_scraper logic runs.
    query_fn   : callable | None
        Injected query function. If None, the real get_all_results is used.
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Allow DATABASE_URL env var to override the hard-coded config
    app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "")

    # Store injectable dependencies on the app so tests can swap them
    app._scraper_fn = scraper_fn
    app._loader_fn  = loader_fn
    app._query_fn   = query_fn

    # ------------------------------------------------------------------
    # Internal runner
    # ------------------------------------------------------------------
    def _run_scraper_default():
        global _scrape_running
        import sys, psycopg2
        from psycopg2 import extras
        from pathlib import Path

        module_dir = os.path.abspath(os.path.dirname(__file__))
        sys.path.insert(0, module_dir)

        try:
            if app._scraper_fn is not None:
                raw_records = app._scraper_fn()
            else:
                from scrape import scrape_data
                raw_records = scrape_data(max_pages=10, output_file=None, start_page=1)

            from clean import clean_data
            cleaned = clean_data(raw_records)

            from query_data import DB_CONFIG
            db_url = app.config.get("DATABASE_URL") or ""
            if db_url:
                conn = psycopg2.connect(db_url)
            else:
                conn = psycopg2.connect(**DB_CONFIG)

            def parse_float(val):
                try:
                    return float(val) if val not in (None, "", "N/A") else None
                except (ValueError, TypeError):
                    return None

            rows = [
                (
                    r.get("program"), r.get("comments"), r.get("date_added"),
                    r.get("url"), r.get("status"), r.get("term"),
                    r.get("US/International"), parse_float(r.get("GPA")),
                    parse_float(r.get("GRE")), parse_float(r.get("GRE V")),
                    parse_float(r.get("GRE AW")), r.get("Degree"),
                    r.get("llm-generated-program"), r.get("llm-generated-university"),
                )
                for r in cleaned
            ]

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
            print(f"✓ Scrape complete. {len(rows)} records processed.")
        except Exception as e:
            print(f"Scraper/load error: {e}")
        finally:
            _set_busy(False)

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        """Render the main analysis page."""
        return render_template("index.html")

    @app.route("/analysis")
    def analysis():
        """Alias for index — the Analysis page."""
        return render_template("index.html")

    @app.route("/api/results")
    def api_results():
        """Return all query results as JSON."""
        try:
            fn = app._query_fn
            if fn is None:
                from query_data import get_all_results
                fn = get_all_results
            data = fn()
            return jsonify({"status": "ok", "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/pull_data", methods=["POST"])
    def api_pull_data():
        """Trigger scraper. Returns 409 if already running."""
        global _scrape_running
        with _scrape_lock:
            if _scrape_running:
                return jsonify({"busy": True, "message": "A data pull is already in progress."}), 409
            _scrape_running = True

        runner = app._loader_fn if app._loader_fn is not None else _run_scraper_default
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()

        return jsonify({"ok": True, "message": "Data pull started!"}), 200

    @app.route("/api/update_analysis", methods=["POST"])
    def api_update_analysis():
        """Refresh analysis. Returns 409 if a pull is in progress."""
        if is_busy():
            return jsonify({"busy": True, "message": "Pull in progress."}), 409
        try:
            fn = app._query_fn
            if fn is None:
                from query_data import get_all_results
                fn = get_all_results
            data = fn()
            return jsonify({"ok": True, "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/scrape_status")
    def api_scrape_status():
        """Return whether a scrape is currently running."""
        return jsonify({"running": is_busy()})

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(host="localhost", port=8080)
