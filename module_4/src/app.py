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
import urllib.parse
import psycopg2
from flask import Flask, jsonify, render_template

from clean import clean_data
from db_config import get_connection
from load_data import create_table, load_records
from query_data import get_all_results
from scrape import scrape_data


# ---------------------------------------------------------------------------
# Thread-safe busy state
#
# Kept as a simple module-level flag + lock (rather than wrapped in a
# class) because the test suite is directly coupled to this exact shape —
# many tests reset state between runs via `app_module._scrape_running =
# False`, bypassing any wrapper entirely. Forcing that onto a class
# instance would either break those tests or require a fragile "kept in
# sync" shim between two sources of truth. The two `global` statements
# below are the deliberate, narrow cost of preserving that contract.
# ---------------------------------------------------------------------------
_scrape_lock = threading.Lock()
_scrape_running = False


def _set_busy(val: bool) -> None:
    """Set the shared busy flag (used by the pipeline and by tests to
    reset state between runs)."""
    global _scrape_running
    with _scrape_lock:
        _scrape_running = val


def is_busy() -> bool:
    """Whether a scrape is currently in progress."""
    return _scrape_running


def _parse_float(val):
    """Convert a value to float or None for empty/invalid inputs."""
    try:
        return float(val) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _connect(db_url: str):
    """Open a DB connection, either from an explicit DATABASE_URL override
    or via db_config's environment-based configuration."""
    if not db_url:
        return get_connection()
    parsed = urllib.parse.urlparse(db_url)
    return psycopg2.connect(
        host=parsed.hostname, port=parsed.port or 5432,
        dbname=parsed.path.lstrip("/"), user=parsed.username,
        password=parsed.password or "",
    )


def _fetch_raw_records(scraper_fn):
    """Get raw scraped records, either from an injected fake (tests) or
    the real scraper (production; requires a live browser, so this branch
    is intentionally excluded from coverage)."""
    if scraper_fn is not None:
        return scraper_fn()
    return scrape_data(max_pages=10, output_file=None, start_page=1)  # pragma: no cover


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
    conn = None
    try:
        raw_records = _fetch_raw_records(scraper_fn)
        cleaned = clean_data(raw_records)
        conn = _connect(db_url)

        # Reuse load_data.py's real insert logic (content_hash-based dedup)
        # instead of a second hand-rolled INSERT — that duplication is what
        # let this path's dedup drift out of sync with load_data.py's in
        # the first place (it fell back to `ON CONFLICT (url)` alone, which
        # silently fails to dedupe records with a missing/malformed url).
        create_table(conn)
        inserted, skipped = load_records(conn, cleaned)
        conn.close()
        print(f"✓ Scrape complete. {inserted} rows inserted, {skipped} skipped.")
    except (psycopg2.Error, RuntimeError, ValueError, TypeError, OSError) as e:
        print(f"Scraper/load error: {e}")
        # If a connection was opened, roll back any partial work and close
        # it. Without this, a failure mid-insert leaves an open transaction
        # holding table locks, and the next pull would inherit a stale
        # connection instead of a clean one.
        try:
            if conn is not None:
                conn.rollback()
                conn.close()
        except psycopg2.Error:
            pass
    finally:
        _set_busy(False)


def _default_runner(app: Flask):
    """Build the background-thread target for a Pull Data request, using
    whatever scraper_fn/loader_fn the app was configured with."""
    loader_fn = app.config.get("LOADER_FN")
    if loader_fn is not None:
        return loader_fn

    scraper_fn = app.config.get("SCRAPER_FN")
    db_url = app.config.get("DATABASE_URL", "")

    def runner():
        run_scraper_pipeline(scraper_fn, db_url=db_url)

    return runner


def _resolve_query_fn(app: Flask):
    """Return the app's injected query_fn, or the real get_all_results."""
    return app.config.get("QUERY_FN") or get_all_results


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
    app.config["SCRAPER_FN"] = scraper_fn
    app.config["LOADER_FN"] = loader_fn
    app.config["QUERY_FN"] = query_fn

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
            data = _resolve_query_fn(app)()
            return jsonify({"status": "ok", "data": data})
        except (psycopg2.Error, KeyError, TypeError, ValueError, RuntimeError) as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/pull_data", methods=["POST"])
    def api_pull_data():
        """Trigger scraper. Returns 409 if already running."""
        global _scrape_running
        with _scrape_lock:
            if _scrape_running:
                return jsonify({
                    "busy": True,
                    "message": "A data pull is already in progress.",
                }), 409
            _scrape_running = True

        thread = threading.Thread(target=_default_runner(app), daemon=True)
        thread.start()

        return jsonify({"ok": True, "message": "Data pull started!"}), 200

    @app.route("/api/update_analysis", methods=["POST"])
    def api_update_analysis():
        """Refresh analysis. Returns 409 if a pull is in progress."""
        if is_busy():
            return jsonify({"busy": True, "message": "Pull in progress."}), 409
        try:
            data = _resolve_query_fn(app)()
            return jsonify({"ok": True, "data": data})
        except (psycopg2.Error, KeyError, TypeError, ValueError, RuntimeError) as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/scrape_status")
    def api_scrape_status():
        """Return whether a scrape is currently running."""
        return jsonify({"running": is_busy()})

    return app


if __name__ == "__main__":  # pragma: no cover
    flask_app = create_app()
    flask_app.run(host="localhost", port=8080)
