"""
tests/test_integration_end_to_end.py
--------------------------------------
End-to-end integration tests: pull → update → render.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import threading
import pytest
import psycopg2
from bs4 import BeautifulSoup
import app as app_module
from conftest import (
    SAMPLE_RECORDS, _insert_records, _reset_table,
    DB_URL, CREATE_TABLE_SQL, INSERT_SQL,
)
import query_data
import urllib.parse as up


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_query_data_config():
    r = up.urlparse(DB_URL)
    query_data.DB_CONFIG.update({
        "host": r.hostname,
        "port": r.port or 5432,
        "dbname": r.path.lstrip("/"),
        "user": r.username,
        "password": r.password or "",
    })


def _make_e2e_app(fake_scraper_records, conn):
    """
    Build an app whose loader:
    - Calls clean_data on the fake records
    - Inserts into the test DB
    - Clears busy state
    """
    from clean import clean_data

    def fake_loader():
        try:
            cleaned = clean_data(fake_scraper_records)
            _insert_records(conn, fake_scraper_records)  # use raw for schema match
        except Exception as e:
            print(f"Integration loader error: {e}")
        finally:
            app_module._set_busy(False)

    _patch_query_data_config()
    app_module._scrape_running = False
    flask_app = app_module.create_app(
        loader_fn=fake_loader,
        query_fn=query_data.get_all_results,
    )
    flask_app.config["TESTING"] = True
    flask_app.config["DATABASE_URL"] = DB_URL
    return flask_app


# ---------------------------------------------------------------------------
# End-to-end: pull → update → render
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_e2e_pull_data_inserts_rows(clean_db):
    """POST /pull_data triggers loader and rows appear in DB."""
    done = threading.Event()
    flask_app = _make_e2e_app(SAMPLE_RECORDS, clean_db)
    client = flask_app.test_client()

    orig_loader = flask_app._loader_fn

    def waiting_loader():
        orig_loader()
        done.set()

    flask_app._loader_fn = waiting_loader

    resp = client.post("/api/pull_data")
    assert resp.status_code == 200
    done.wait(timeout=5)

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == len(SAMPLE_RECORDS)


@pytest.mark.integration
def test_e2e_update_analysis_returns_200_after_pull(clean_db):
    """After pull completes, POST /update_analysis returns 200."""
    done = threading.Event()
    flask_app = _make_e2e_app(SAMPLE_RECORDS, clean_db)
    client = flask_app.test_client()

    orig_loader = flask_app._loader_fn

    def waiting_loader():
        orig_loader()
        done.set()

    flask_app._loader_fn = waiting_loader

    client.post("/api/pull_data")
    done.wait(timeout=5)

    resp = client.post("/api/update_analysis")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


@pytest.mark.integration
def test_e2e_render_shows_updated_analysis(clean_db):
    """After pull + update, /api/results includes correct fall_2026_count."""
    done = threading.Event()
    flask_app = _make_e2e_app(SAMPLE_RECORDS, clean_db)
    client = flask_app.test_client()

    orig_loader = flask_app._loader_fn

    def waiting_loader():
        orig_loader()
        done.set()

    flask_app._loader_fn = waiting_loader

    client.post("/api/pull_data")
    done.wait(timeout=5)

    resp = client.get("/api/results")
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["data"]["fall_2026_count"] == len(SAMPLE_RECORDS)


@pytest.mark.integration
def test_e2e_pct_international_correctly_formatted(clean_db):
    """After pull, pct_international is a float (two-decimal-safe)."""
    done = threading.Event()
    flask_app = _make_e2e_app(SAMPLE_RECORDS, clean_db)
    client = flask_app.test_client()

    orig_loader = flask_app._loader_fn

    def waiting_loader():
        orig_loader()
        done.set()

    flask_app._loader_fn = waiting_loader

    client.post("/api/pull_data")
    done.wait(timeout=5)

    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    pct = data["pct_international"]
    assert isinstance(pct, float)
    formatted = f"{pct:.2f}%"
    import re
    assert re.match(r"\d+\.\d{2}%", formatted)


# ---------------------------------------------------------------------------
# Multiple pulls — uniqueness
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_e2e_double_pull_no_duplicates(clean_db):
    """Running pull twice with the same records does not duplicate rows."""
    done1 = threading.Event()
    done2 = threading.Event()
    call_count = [0]

    def make_loader(event):
        def loader():
            try:
                _insert_records(clean_db, SAMPLE_RECORDS)
            finally:
                call_count[0] += 1
                app_module._set_busy(False)
                event.set()
        return loader

    app_module._scrape_running = False
    _patch_query_data_config()
    flask_app = app_module.create_app(
        loader_fn=make_loader(done1),
        query_fn=query_data.get_all_results,
    )
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    # First pull
    client.post("/api/pull_data")
    done1.wait(timeout=5)

    # Second pull — swap loader, reset busy
    flask_app._loader_fn = make_loader(done2)
    client.post("/api/pull_data")
    done2.wait(timeout=5)

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]

    assert count == len(SAMPLE_RECORDS), (
        f"Expected {len(SAMPLE_RECORDS)} rows after duplicate pull, got {count}"
    )


@pytest.mark.integration
def test_e2e_overlapping_data_consistent(clean_db):
    """Pull with overlap (some new, some existing) yields correct final count."""
    extra = {
        "program": "Biology, Yale",
        "comments": "",
        "date_added": "2024-04-01",
        "url": "https://thegradcafe.com/result/99",
        "status": "Accepted on Apr 01",
        "term": "Fall 2026",
        "US/International": "International",
        "GPA": "3.7",
        "GRE": None, "GRE V": None, "GRE AW": None,
        "Degree": "PhD",
        "llm-generated-program": "Biology",
        "llm-generated-university": "Yale University",
    }

    # First pull: original records
    _insert_records(clean_db, SAMPLE_RECORDS)

    # Second pull: original + 1 new
    _insert_records(clean_db, SAMPLE_RECORDS + [extra])

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]

    assert count == len(SAMPLE_RECORDS) + 1


@pytest.mark.integration
def test_e2e_analysis_page_renders_after_pull(clean_db):
    """After pull completes, GET /analysis renders HTML with 'Answer:' labels."""
    done = threading.Event()
    flask_app = _make_e2e_app(SAMPLE_RECORDS, clean_db)
    client = flask_app.test_client()

    orig_loader = flask_app._loader_fn

    def waiting_loader():
        orig_loader()
        done.set()

    flask_app._loader_fn = waiting_loader

    client.post("/api/pull_data")
    done.wait(timeout=5)

    resp = client.get("/analysis")
    assert resp.status_code == 200
    html = resp.data
    soup = BeautifulSoup(html, "html.parser")

    # Page must include structural markers present after data is available
    assert b"Answer:" in html, "Rendered /analysis page missing 'Answer:' labels"
    assert soup.find(attrs={"data-testid": "pull-data-btn"}) is not None
    assert soup.find(attrs={"data-testid": "update-analysis-btn"}) is not None


@pytest.mark.integration
def test_e2e_analysis_page_reflects_api_results_after_update(clean_db):
    """After pull + update_analysis, /api/results data keys match /analysis page structure."""
    done = threading.Event()
    flask_app = _make_e2e_app(SAMPLE_RECORDS, clean_db)
    client = flask_app.test_client()

    orig_loader = flask_app._loader_fn

    def waiting_loader():
        orig_loader()
        done.set()

    flask_app._loader_fn = waiting_loader

    client.post("/api/pull_data")
    done.wait(timeout=5)

    # Trigger update_analysis
    update_resp = client.post("/api/update_analysis")
    assert update_resp.status_code == 200
    update_data = update_resp.get_json()["data"]

    # Verify /analysis page still renders cleanly after update
    page_resp = client.get("/analysis")
    assert page_resp.status_code == 200
    assert b"Analysis" in page_resp.data

    # The data from update_analysis must include expected keys
    assert "fall_2026_count" in update_data
    assert update_data["fall_2026_count"] == len(SAMPLE_RECORDS)


@pytest.mark.integration
def test_e2e_busy_blocks_update_during_pull(clean_db):
    """While pull is in progress, update_analysis returns 409."""
    done = threading.Event()
    started = threading.Event()

    def slow_loader():
        started.set()
        done.wait(timeout=5)
        app_module._set_busy(False)

    app_module._scrape_running = False
    _patch_query_data_config()
    flask_app = app_module.create_app(
        loader_fn=slow_loader,
        query_fn=query_data.get_all_results,
    )
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    client.post("/api/pull_data")
    started.wait(timeout=3)

    resp = client.post("/api/update_analysis")
    done.set()
    assert resp.status_code == 409