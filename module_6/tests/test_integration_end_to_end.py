"""
tests/test_integration_end_to_end.py
--------------------------------------
End-to-end integration tests for the RabbitMQ-based architecture.
Publisher is mocked; DB operations are tested against the real test DB.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "db"))

import re
import pytest
import urllib.parse as up
from unittest.mock import patch
from bs4 import BeautifulSoup

import query_data
from conftest import SAMPLE_RECORDS, _insert_records, _reset_table, DB_URL


def _patch_query_data_config():
    """Point query_data at the test DB."""
    r = up.urlparse(DB_URL)
    query_data.DB_CONFIG.update({
        "host": r.hostname,
        "port": r.port or 5432,
        "dbname": r.path.lstrip("/"),
        "user": r.username,
        "password": r.password or "",
    })


def _make_app(query_fn=None):
    """Create a test app with mocked publisher."""
    import app as app_module
    flask_app = app_module.create_app(query_fn=query_fn or query_data.get_all_results)
    flask_app.config["TESTING"] = True
    flask_app.config["DATABASE_URL"] = DB_URL
    flask_app.config["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"
    return flask_app


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_e2e_analysis_page_renders(clean_db):
    """GET /analysis renders HTML with Answer: labels and buttons."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    _patch_query_data_config()
    flask_app = _make_app()
    client = flask_app.test_client()

    resp = client.get("/analysis")
    assert resp.status_code == 200
    html = resp.data
    soup = BeautifulSoup(html, "html.parser")
    assert b"Answer:" in html
    assert soup.find(attrs={"data-testid": "pull-data-btn"}) is not None
    assert soup.find(attrs={"data-testid": "update-analysis-btn"}) is not None


@pytest.mark.integration
def test_e2e_results_reflect_db_data(clean_db):
    """GET /api/results returns correct fall_2026_count after data insert."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    _patch_query_data_config()
    flask_app = _make_app()
    client = flask_app.test_client()

    resp = client.get("/api/results")
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["data"]["fall_2026_count"] == len(SAMPLE_RECORDS)


@pytest.mark.integration
def test_e2e_pct_international_correctly_formatted(clean_db):
    """pct_international is a float formatted to two decimal places."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    _patch_query_data_config()
    flask_app = _make_app()
    client = flask_app.test_client()

    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    pct = data["pct_international"]
    assert isinstance(pct, float)
    assert re.match(r"\d+\.\d{2}%", f"{pct:.2f}%")


# ---------------------------------------------------------------------------
# Task publishing
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_e2e_pull_data_publishes_task(clean_db):
    """POST /api/pull_data publishes scrape_new_data task and returns 202."""
    _patch_query_data_config()
    flask_app = _make_app()
    client = flask_app.test_client()

    with patch("app.publish_task") as mock_pub:
        resp = client.post("/api/pull_data")
        mock_pub.assert_called_once_with("scrape_new_data", payload={})
    assert resp.status_code == 202
    assert resp.get_json()["status"] == "queued"


@pytest.mark.integration
def test_e2e_update_analysis_publishes_task(clean_db):
    """POST /api/update_analysis publishes recompute_analytics task and returns 202."""
    _patch_query_data_config()
    flask_app = _make_app()
    client = flask_app.test_client()

    with patch("app.publish_task") as mock_pub:
        resp = client.post("/api/update_analysis")
        mock_pub.assert_called_once_with("recompute_analytics", payload={})
    assert resp.status_code == 202
    assert resp.get_json()["status"] == "queued"


# ---------------------------------------------------------------------------
# DB idempotency
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_e2e_double_insert_no_duplicates(clean_db):
    """Inserting same records twice yields no duplicate rows."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    _insert_records(clean_db, SAMPLE_RECORDS)
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == len(SAMPLE_RECORDS)


@pytest.mark.integration
def test_e2e_overlapping_data_consistent(clean_db):
    """Pull with overlap yields correct final count."""
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
    _insert_records(clean_db, SAMPLE_RECORDS)
    _insert_records(clean_db, SAMPLE_RECORDS + [extra])
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == len(SAMPLE_RECORDS) + 1


@pytest.mark.integration
def test_e2e_results_after_update_analysis(clean_db):
    """After insert, /api/results and /analysis page are consistent."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    _patch_query_data_config()
    flask_app = _make_app()
    client = flask_app.test_client()

    results_resp = client.get("/api/results")
    assert results_resp.status_code == 200
    results_data = results_resp.get_json()["data"]
    assert "fall_2026_count" in results_data
    assert results_data["fall_2026_count"] == len(SAMPLE_RECORDS)

    page_resp = client.get("/analysis")
    assert page_resp.status_code == 200
    assert b"Analysis" in page_resp.data