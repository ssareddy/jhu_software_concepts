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
import sys
import threading
import urllib.parse as up

import psycopg2
import psycopg2.extras as pg_extras
from flask import Flask, jsonify, render_template

from clean import clean_data
from db_config import get_connection
from query_data import get_all_results
from scrape import scrape_data


# ---------------------------------------------------------------------------
# Thread-safe busy state
# ---------------------------------------------------------------------------

class _BusyState:
    """Thread-safe container for the scrape-running flag."""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False

    def set(self, val: bool) -> None:
        """Set the running flag."""
        with self._lock:
            self._running = val

    def get(self) -> bool:
        """Return the current running flag."""
        return self._running

    def acquire(self) -> bool:
        """Set to True if not already running. Returns True if acquired."""
        with self._lock:
            if self._running:
                return False
            self._running = True
            return True


_busy = _BusyState()


def _parse_float(val):
    """Convert a value to float or None for empty/invalid inputs."""
    try:
        return float(val) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _build_connection(db_url: str):
    """Return a psycopg2 connection from a DATABASE_URL string or env config."""
    if db_url:
        parsed = up.urlparse(db_url)
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password or "",
        )
    return get_connection()


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
    module_dir = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, module_dir)

    try:
        if scraper_fn is not None:
            raw_records = scraper_fn()
        else:
            raw_records = scrape_data(  # pragma: no cover
                max_pages=10, output_file=None, start_page=1
            )

        cleaned = clean_data(raw_records)
        conn = _build_connection(db_url)

        rows = [
            (
                rec.get("program"), rec.get("comments"), rec.get("date_added"),
                rec.get("url"), rec.get("status"), rec.get("term"),
                rec.get("US/International"), _parse_float(rec.get("GPA")),
                _parse_float(rec.get("GRE")), _parse_float(rec.get("GRE V")),
                _parse_float(rec.get("GRE AW")), rec.get("Degree"),
                rec.get("llm-generated-program"), rec.get("llm-generated-university"),
            )
            for rec in cleaned
        ]

        insert_sql = """
            INSERT INTO applicants (
                program, comments, date_added, url, status, term,
                us_or_international, gpa, gre, gre_v, gre_aw, degree,
                llm_generated_program, llm_generated_university
            ) VALUES %s
            ON CONFLICT (url) DO NOTHING;
        """
        with conn.cursor() as cur:
            pg_extras.execute_values(cur, insert_sql, rows, page_size=500)
        conn.commit()
        conn.close()
        print(f"Scrape complete. {len(rows)} records processed.")
    except (psycopg2.DatabaseError, OSError, ValueError, RuntimeError) as exc:
        print(f"Scraper/load error: {exc}")
    finally:
        _busy.set(False)


def _get_query_fn(flask_app):
    """Resolve the query function from injection or the real module."""
    fn = flask_app.config.get("QUERY_FN")
    if fn is None:
        fn = get_all_results
    return fn


def create_app(scraper_fn=None, loader_fn=None, query_fn=None):
    """
    Application factory.

    Parameters
    ----------
    scraper_fn : callable | None
        Injected scraper replacing scrape_data (for tests).
    loader_fn : callable | None
        Fully replaces the entire scrape→clean→insert pipeline (for tests).
    query_fn : callable | None
        Injected query function replacing get_all_results (for tests).
    """
    flask_app = Flask(__name__, template_folder="templates", static_folder="static")
    flask_app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "")
    flask_app.config["SCRAPER_FN"] = scraper_fn
    flask_app.config["LOADER_FN"] = loader_fn
    flask_app.config["QUERY_FN"] = query_fn

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @flask_app.route("/")
    def index():
        """Render the main analysis page."""
        return render_template("index.html")

    @flask_app.route("/analysis")
    def analysis():
        """Alias for index — the Analysis page."""
        return render_template("index.html")

    @flask_app.route("/api/results")
    def api_results():
        """Return all query results as JSON."""
        try:
            data = _get_query_fn(flask_app)()
            return jsonify({"status": "ok", "data": data})
        except (psycopg2.DatabaseError, OSError, RuntimeError) as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

    @flask_app.route("/api/pull_data", methods=["POST"])
    def api_pull_data():
        """Trigger scraper. Returns 409 if already running."""
        if not _busy.acquire():
            return jsonify(
                {"busy": True, "message": "A data pull is already in progress."}
            ), 409

        db_url = flask_app.config.get("DATABASE_URL", "")
        active_loader = flask_app.config.get("LOADER_FN")

        if active_loader is not None:
            runner = active_loader
        else:
            active_scraper = flask_app.config.get("SCRAPER_FN")

            def runner():
                """Wrap pipeline so scraper_fn is captured at call time."""
                run_scraper_pipeline(active_scraper, db_url=db_url)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return jsonify({"ok": True, "message": "Data pull started!"}), 200

    @flask_app.route("/api/update_analysis", methods=["POST"])
    def api_update_analysis():
        """Refresh analysis. Returns 409 if a pull is in progress."""
        if _busy.get():
            return jsonify({"busy": True, "message": "Pull in progress."}), 409
        try:
            data = _get_query_fn(flask_app)()
            return jsonify({"ok": True, "data": data})
        except (psycopg2.DatabaseError, OSError, RuntimeError) as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

    @flask_app.route("/api/scrape_status")
    def api_scrape_status():
        """Return whether a scrape is currently running."""
        return jsonify({"running": _busy.get()})

    return flask_app


if __name__ == "__main__":  # pragma: no cover
    app = create_app()
    app.run(host="localhost", port=8080)
