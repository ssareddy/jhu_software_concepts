"""
tests/test_flask_page.py
------------------------
Flask App & Page Rendering tests.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web"))

import pytest
from bs4 import BeautifulSoup
from unittest.mock import patch


# ---------------------------------------------------------------------------
# App factory / config
# ---------------------------------------------------------------------------

@pytest.mark.web
def test_create_app_returns_flask_app(app):
    """create_app() returns a Flask application object."""
    from flask import Flask
    assert isinstance(app, Flask)


@pytest.mark.web
def test_app_has_testing_config(app):
    """TESTING flag is set in the test app."""
    assert app.config["TESTING"] is True


@pytest.mark.web
def test_app_has_required_routes(app):
    """All required URL rules are registered."""
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/" in rules
    assert "/analysis" in rules
    assert "/api/results" in rules
    assert "/api/pull_data" in rules
    assert "/api/update_analysis" in rules
    assert "/api/scrape_status" in rules


# ---------------------------------------------------------------------------
# GET /analysis — page load
# ---------------------------------------------------------------------------

@pytest.mark.web
def test_analysis_returns_200(client):
    """GET /analysis returns HTTP 200."""
    resp = client.get("/analysis")
    assert resp.status_code == 200


@pytest.mark.web
def test_index_returns_200(client):
    """GET / returns HTTP 200."""
    resp = client.get("/")
    assert resp.status_code == 200


@pytest.mark.web
def test_page_contains_pull_data_button(client):
    """Page HTML contains an element with data-testid='pull-data-btn'."""
    resp = client.get("/analysis")
    soup = BeautifulSoup(resp.data, "html.parser")
    btn = soup.find(attrs={"data-testid": "pull-data-btn"})
    assert btn is not None


@pytest.mark.web
def test_page_contains_update_analysis_button(client):
    """Page HTML contains an element with data-testid='update-analysis-btn'."""
    resp = client.get("/analysis")
    soup = BeautifulSoup(resp.data, "html.parser")
    btn = soup.find(attrs={"data-testid": "update-analysis-btn"})
    assert btn is not None


@pytest.mark.web
def test_page_contains_analysis_text(client):
    """Page text includes the word 'Analysis'."""
    resp = client.get("/analysis")
    assert b"Analysis" in resp.data


@pytest.mark.web
def test_page_contains_answer_label(client):
    """Page HTML includes at least one 'Answer:' label."""
    resp = client.get("/analysis")
    assert b"Answer:" in resp.data


@pytest.mark.web
def test_pull_data_button_text(client):
    """Pull Data button displays 'Pull Data' text."""
    resp = client.get("/analysis")
    soup = BeautifulSoup(resp.data, "html.parser")
    btn = soup.find(attrs={"data-testid": "pull-data-btn"})
    assert btn is not None
    assert "Pull Data" in btn.get_text()


@pytest.mark.web
def test_update_analysis_button_text(client):
    """Update Analysis button displays 'Update Analysis' text."""
    resp = client.get("/analysis")
    soup = BeautifulSoup(resp.data, "html.parser")
    btn = soup.find(attrs={"data-testid": "update-analysis-btn"})
    assert btn is not None
    assert "Update Analysis" in btn.get_text()


# ---------------------------------------------------------------------------
# POST endpoints return 202
# ---------------------------------------------------------------------------

@pytest.mark.web
def test_pull_data_returns_202(client):
    """POST /api/pull_data returns 202."""
    with patch("app.app.publish_task"):
        resp = client.post("/api/pull_data")
    assert resp.status_code == 202


@pytest.mark.web
def test_update_analysis_returns_202(client):
    """POST /api/update_analysis returns 202."""
    with patch("app.app.publish_task"):
        resp = client.post("/api/update_analysis")
    assert resp.status_code == 202


@pytest.mark.web
def test_scrape_status_returns_worker_managed(client):
    """GET /api/scrape_status returns worker_managed."""
    resp = client.get("/api/scrape_status")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "worker_managed"