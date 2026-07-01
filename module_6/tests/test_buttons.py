"""
tests/test_buttons.py
---------------------
Button endpoint tests for the RabbitMQ-based architecture.
Buttons now publish tasks and return 202 immediately.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web", "app"))

import pytest
from unittest.mock import patch, MagicMock


def _make_app(query_fn=None):
    """Create a fresh test app with mocked publisher."""
    import app as app_module

    def _default_query():
        return {
            "fall_2026_count": 1, "pct_international": 0.0,
            "avg_gpa": 3.5, "avg_gre": 0.0, "avg_gre_v": 0.0, "avg_gre_aw": 0.0,
            "avg_gpa_american": 0.0, "pct_accepted_fall_2026": 100.0,
            "avg_gpa_accepted": 3.5, "jhu_ms_cs_count": 0,
            "q8_scraped": 0, "q9_llm": 0,
            "q10_degree_gpa": [], "q11_nationality_acceptance": [],
        }

    flask_app = app_module.create_app(query_fn=query_fn or _default_query)
    flask_app.config["TESTING"] = True
    flask_app.config["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"
    return flask_app


# ---------------------------------------------------------------------------
# POST /api/pull_data
# ---------------------------------------------------------------------------

@pytest.mark.buttons
def test_pull_data_returns_202_when_published():
    """POST /api/pull_data returns 202 with status=queued when published."""
    flask_app = _make_app()
    client = flask_app.test_client()
    with patch("app.publish_task") as mock_pub:
        resp = client.post("/api/pull_data")
        mock_pub.assert_called_once_with("scrape_new_data", payload={})
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] == "queued"
    assert data["task"] == "scrape_new_data"


@pytest.mark.buttons
def test_pull_data_calls_publish_task():
    """POST /api/pull_data calls publish_task with correct kind."""
    flask_app = _make_app()
    client = flask_app.test_client()
    with patch("app.publish_task") as mock_pub:
        client.post("/api/pull_data")
        mock_pub.assert_called_once_with("scrape_new_data", payload={})


@pytest.mark.buttons
def test_pull_data_returns_503_on_publish_failure():
    """POST /api/pull_data returns 503 when RabbitMQ publish fails."""
    flask_app = _make_app()
    client = flask_app.test_client()
    with patch("app.publish_task", side_effect=RuntimeError("RabbitMQ down")):
        resp = client.post("/api/pull_data")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["error"] == "publish_failed"


@pytest.mark.buttons
def test_pull_data_returns_503_on_os_error():
    """POST /api/pull_data returns 503 on OSError."""
    flask_app = _make_app()
    client = flask_app.test_client()
    with patch("app.publish_task", side_effect=OSError("connection failed")):
        resp = client.post("/api/pull_data")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/update_analysis
# ---------------------------------------------------------------------------

@pytest.mark.buttons
def test_update_analysis_returns_202_when_published():
    """POST /api/update_analysis returns 202 with status=queued."""
    flask_app = _make_app()
    client = flask_app.test_client()
    with patch("app.publish_task") as mock_pub:
        resp = client.post("/api/update_analysis")
        mock_pub.assert_called_once_with("recompute_analytics", payload={})
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] == "queued"
    assert data["task"] == "recompute_analytics"


@pytest.mark.buttons
def test_update_analysis_calls_publish_task():
    """POST /api/update_analysis calls publish_task with correct kind."""
    flask_app = _make_app()
    client = flask_app.test_client()
    with patch("app.publish_task") as mock_pub:
        client.post("/api/update_analysis")
        mock_pub.assert_called_once_with("recompute_analytics", payload={})


@pytest.mark.buttons
def test_update_analysis_returns_503_on_publish_failure():
    """POST /api/update_analysis returns 503 when RabbitMQ publish fails."""
    flask_app = _make_app()
    client = flask_app.test_client()
    with patch("app.publish_task", side_effect=RuntimeError("RabbitMQ down")):
        resp = client.post("/api/update_analysis")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["error"] == "publish_failed"


@pytest.mark.buttons
def test_update_analysis_returns_503_on_os_error():
    """POST /api/update_analysis returns 503 on OSError."""
    flask_app = _make_app()
    client = flask_app.test_client()
    with patch("app.publish_task", side_effect=OSError("connection failed")):
        resp = client.post("/api/update_analysis")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/scrape_status
# ---------------------------------------------------------------------------

@pytest.mark.buttons
def test_scrape_status_returns_worker_managed(client):
    """GET /api/scrape_status returns worker_managed status."""
    resp = client.get("/api/scrape_status")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "worker_managed"


# ---------------------------------------------------------------------------
# GET /api/results
# ---------------------------------------------------------------------------

@pytest.mark.buttons
def test_api_results_returns_200(client):
    """GET /api/results returns 200 with ok status."""
    resp = client.get("/api/results")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


@pytest.mark.buttons
def test_api_results_returns_data(client):
    """GET /api/results returns data dict."""
    resp = client.get("/api/results")
    data = resp.get_json()
    assert "data" in data
    assert "fall_2026_count" in data["data"]


@pytest.mark.buttons
def test_api_results_returns_500_on_db_error():
    """GET /api/results returns 500 when query function raises."""
    import app as app_module

    def failing_query():
        raise RuntimeError("DB error")

    flask_app = app_module.create_app(query_fn=failing_query)
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()
    resp = client.get("/api/results")
    assert resp.status_code == 500
    assert resp.get_json()["status"] == "error"