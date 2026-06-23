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

# ---------------------------------------------------------------------------
# Thread-safe busy state
# ---------------------------------------------------------------------------
_scrape_lock = threading.Lock()
_SCRAPE_RUNNING = False


def _set_busy(val: bool) -> None:
    """Set the global scrape-running flag inside the lock."""
    global _SCRAPE_RUNNING  # pylint: disable=global-statement
    with _scrape_lock:
        _SCRAPE_RUNNING = val


def is_busy() -> bool:
    """Return True if a scrape is currently in progress."""
    return _SCRAPE_RUNNING


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
    from db_config import get_connection  # pylint: disable=import-outside-toplevel
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
            from scrape import scrape_data  # pragma: no cover  # pylint: disable=import-outside-toplevel
            raw_records = scrape_data(  # pragma: no cover
                max_pages=10, output_file=None, start_page=1
            )

        from clean import clean_data  # pylint: disable=import-outside-toplevel
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
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Scraper/load error: {exc}")
    finally:
        _set_busy(False)


def _get_query_fn(flask_app):
    """Resolve the query function from injection or the real module."""
    fn = flask_app.config.get("QUERY_FN")
    if fn is None:
        from query_data import get_all_results  # pylint: disable=import-outside-toplevel
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

    # Keep underscore attributes for backwards-compat with existing tests
    flask_app._scraper_fn = scraper_fn  # pylint: disable=protected-access
    flask_app._loader_fn = loader_fn    # pylint: disable=protected-access
    flask_app._query_fn = query_fn      # pylint: disable=protected-access

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
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return jsonify({"status": "error", "message": str(exc)}), 500

    @flask_app.route("/api/pull_data", methods=["POST"])
    def api_pull_data():
        """Trigger scraper. Returns 409 if already running."""
        global _SCRAPE_RUNNING  # pylint: disable=global-statement
        with _scrape_lock:
            if _SCRAPE_RUNNING:
                return jsonify(
                    {"busy": True, "message": "A data pull is already in progress."}
                ), 409
            _SCRAPE_RUNNING = True

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
        if is_busy():
            return jsonify({"busy": True, "message": "Pull in progress."}), 409
        try:
            data = _get_query_fn(flask_app)()
            return jsonify({"ok": True, "data": data})
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return jsonify({"status": "error", "message": str(exc)}), 500

    @flask_app.route("/api/scrape_status")
    def api_scrape_status():
        """Return whether a scrape is currently running."""
        return jsonify({"running": is_busy()})

    return flask_app


if __name__ == "__main__":  # pragma: no cover
    app = create_app()
    app.run(host="localhost", port=8080)
