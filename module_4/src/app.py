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
# Thread-safe busy state
# ---------------------------------------------------------------------------
_scrape_lock = threading.Lock()
_scrape_running = False


def _set_busy(val: bool) -> None:
    global _scrape_running
    with _scrape_lock:
        _scrape_running = val


def is_busy() -> bool:
    return _scrape_running


def _parse_float(val):
    """Convert a value to float or None for empty/invalid inputs."""
    try:
        return float(val) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def run_scraper_pipeline(scraper_fn, db_url=""):
    """
    Execute the full scrape → clean → insert pipeline.

    Parameters
    ----------
    scraper_fn : callable | None
        If provided, called instead of the real scrape_data.
    db_url : str
        DATABASE_URL override for the DB connection.
    """
    import sys
    import psycopg2
    from psycopg2 import extras

    module_dir = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, module_dir)

    try:
        if scraper_fn is not None:
            raw_records = scraper_fn()
        else:
            from scrape import scrape_data  # pragma: no cover
            raw_records = scrape_data(max_pages=10, output_file=None, start_page=1)  # pragma: no cover

        from clean import clean_data
        cleaned = clean_data(raw_records)

        from db_config import get_connection, get_db_config
        if db_url:
            import urllib.parse as up
            r = up.urlparse(db_url)
            conn = psycopg2.connect(
                host=r.hostname, port=r.port or 5432,
                dbname=r.path.lstrip("/"), user=r.username,
                password=r.password or "",
            )
        else:
            conn = get_connection()

        rows = [
            (
                r.get("program"), r.get("comments"), r.get("date_added"),
                r.get("url"), r.get("status"), r.get("term"),
                r.get("US/International"), _parse_float(r.get("GPA")),
                _parse_float(r.get("GRE")), _parse_float(r.get("GRE V")),
                _parse_float(r.get("GRE AW")), r.get("Degree"),
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


def create_app(scraper_fn=None, loader_fn=None, query_fn=None):
    """
    Application factory.

    Parameters
    ----------
    scraper_fn : callable | None
        Injected scraper replacing scrape_data (for tests).
    loader_fn  : callable | None
        Fully replaces the entire scrape→clean→insert pipeline (for tests).
    query_fn   : callable | None
        Injected query function replacing get_all_results (for tests).
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "")

    app._scraper_fn = scraper_fn
    app._loader_fn  = loader_fn
    app._query_fn   = query_fn

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

        db_url = app.config.get("DATABASE_URL", "")

        if app._loader_fn is not None:
            runner = app._loader_fn
        else:
            def runner():
                run_scraper_pipeline(app._scraper_fn, db_url=db_url)

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


if __name__ == "__main__":  # pragma: no cover
    app = create_app()
    app.run(host="localhost", port=8080)