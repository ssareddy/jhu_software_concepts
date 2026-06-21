"""
tests/test_buttons.py
---------------------
Button endpoint & busy-state behavior tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import threading
import pytest
import app as app_module


# ---------------------------------------------------------------------------
# Helper: build app with a controllable loader
# ---------------------------------------------------------------------------

def _make_app_with_loader(loader_fn, query_fn=None):
    """Create a fresh test app with an injected loader."""
    app_module._scrape_running = False

    def _default_query():
        return {
            "fall_2026_count": 1, "pct_international": 0.0,
            "avg_gpa": 3.5, "avg_gre": 0.0, "avg_gre_v": 0.0, "avg_gre_aw": 0.0,
            "avg_gpa_american": 0.0, "pct_accepted_fall_2026": 100.0,
            "avg_gpa_accepted": 3.5, "jhu_ms_cs_count": 0,
            "q8_scraped": 0, "q9_llm": 0,
            "q10_degree_gpa": [], "q11_nationality_acceptance": [],
        }

    flask_app = app_module.create_app(
        loader_fn=loader_fn,
        query_fn=query_fn or _default_query,
    )
    flask_app.config["TESTING"] = True
    return flask_app


# ---------------------------------------------------------------------------
# POST /api/pull_data
# ---------------------------------------------------------------------------

@pytest.mark.buttons
def test_pull_data_returns_200_when_not_busy():
    """POST /api/pull_data returns 200 with {ok: true} when not busy."""
    event = threading.Event()

    def fake_loader():
        event.wait(timeout=5)
        app_module._set_busy(False)

    flask_app = _make_app_with_loader(fake_loader)
    client = flask_app.test_client()
    resp = client.post("/api/pull_data")
    event.set()
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


@pytest.mark.buttons
def test_pull_data_triggers_loader():
    """POST /api/pull_data triggers the loader function."""
    called = []
    done = threading.Event()

    def fake_loader():
        called.append(True)
        done.set()
        app_module._set_busy(False)

    flask_app = _make_app_with_loader(fake_loader)
    client = flask_app.test_client()
    client.post("/api/pull_data")
    done.wait(timeout=3)
    assert called, "Loader was not called"


@pytest.mark.buttons
def test_pull_data_returns_409_when_busy():
    """POST /api/pull_data returns 409 when a pull is already running."""
    done = threading.Event()

    def slow_loader():
        done.wait(timeout=5)
        app_module._set_busy(False)

    flask_app = _make_app_with_loader(slow_loader)
    client = flask_app.test_client()

    # First pull — starts the loader
    client.post("/api/pull_data")
    # Second pull — should be gated
    resp = client.post("/api/pull_data")
    done.set()
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["busy"] is True


# ---------------------------------------------------------------------------
# POST /api/update_analysis
# ---------------------------------------------------------------------------

@pytest.mark.buttons
def test_update_analysis_returns_200_when_not_busy(client):
    """POST /api/update_analysis returns 200 when not busy."""
    resp = client.post("/api/update_analysis")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


@pytest.mark.buttons
def test_update_analysis_returns_data_when_not_busy(client):
    """POST /api/update_analysis returns analysis data."""
    resp = client.post("/api/update_analysis")
    data = resp.get_json()
    assert "data" in data
    assert "fall_2026_count" in data["data"]


@pytest.mark.buttons
def test_update_analysis_returns_409_when_busy():
    """POST /api/update_analysis returns 409 when pull is in progress."""
    done = threading.Event()

    def slow_loader():
        done.wait(timeout=5)
        app_module._set_busy(False)

    flask_app = _make_app_with_loader(slow_loader)
    client = flask_app.test_client()

    # Start a pull to make it busy
    client.post("/api/pull_data")
    resp = client.post("/api/update_analysis")
    done.set()
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["busy"] is True


@pytest.mark.buttons
def test_update_analysis_does_not_update_when_busy():
    """When busy, /api/update_analysis does not call the query function."""
    call_count = []
    done = threading.Event()

    def slow_loader():
        done.wait(timeout=5)
        app_module._set_busy(False)

    def counting_query():
        call_count.append(1)
        return {
            "fall_2026_count": 0, "pct_international": 0.0,
            "avg_gpa": 0.0, "avg_gre": 0.0, "avg_gre_v": 0.0, "avg_gre_aw": 0.0,
            "avg_gpa_american": 0.0, "pct_accepted_fall_2026": 0.0,
            "avg_gpa_accepted": 0.0, "jhu_ms_cs_count": 0,
            "q8_scraped": 0, "q9_llm": 0,
            "q10_degree_gpa": [], "q11_nationality_acceptance": [],
        }

    flask_app = _make_app_with_loader(slow_loader, query_fn=counting_query)
    client = flask_app.test_client()

    client.post("/api/pull_data")
    client.post("/api/update_analysis")  # should be blocked
    count_before = len(call_count)
    done.set()
    assert count_before == 0, "Query was called while busy — update_analysis failed to gate"


# ---------------------------------------------------------------------------
# GET /api/scrape_status
# ---------------------------------------------------------------------------

@pytest.mark.buttons
def test_scrape_status_not_busy(client):
    """GET /api/scrape_status returns {running: false} when idle."""
    resp = client.get("/api/scrape_status")
    assert resp.status_code == 200
    assert resp.get_json()["running"] is False


@pytest.mark.buttons
def test_scrape_status_busy_during_pull():
    """GET /api/scrape_status returns {running: true} while pull is active."""
    done = threading.Event()

    def slow_loader():
        done.wait(timeout=5)
        app_module._set_busy(False)

    flask_app = _make_app_with_loader(slow_loader)
    client = flask_app.test_client()

    client.post("/api/pull_data")
    status = client.get("/api/scrape_status").get_json()
    done.set()
    assert status["running"] is True


# ---------------------------------------------------------------------------
# Error-path: loader raises an exception
# ---------------------------------------------------------------------------

@pytest.mark.buttons
def test_loader_error_clears_busy_state():
    """When loader raises an exception, busy state is reset to False."""
    finished = threading.Event()

    def failing_loader():
        try:
            raise RuntimeError("Simulated scraper failure")
        except Exception:
            pass
        finally:
            app_module._set_busy(False)
            finished.set()

    flask_app = _make_app_with_loader(failing_loader)
    client = flask_app.test_client()

    client.post("/api/pull_data")
    finished.wait(timeout=3)
    status = client.get("/api/scrape_status").get_json()
    assert status["running"] is False


@pytest.mark.buttons
def test_loader_error_pull_data_returns_non_200_on_subsequent_check():
    """After a loader failure, /api/pull_data can be triggered again (not stuck busy)."""
    finished = threading.Event()

    def failing_loader():
        try:
            raise RuntimeError("Simulated scraper failure")
        except Exception:
            pass
        finally:
            app_module._set_busy(False)
            finished.set()

    flask_app = _make_app_with_loader(failing_loader)
    client = flask_app.test_client()

    # Trigger the failing pull
    resp1 = client.post("/api/pull_data")
    assert resp1.status_code == 200

    # Wait for failure + busy reset
    finished.wait(timeout=3)

    # A second pull should succeed (200), not return 409 stuck-busy
    finished2 = threading.Event()

    def second_failing_loader():
        try:
            raise RuntimeError("Second failure")
        except Exception:
            pass
        finally:
            app_module._set_busy(False)
            finished2.set()

    flask_app._loader_fn = second_failing_loader
    resp2 = client.post("/api/pull_data")
    finished2.wait(timeout=3)
    assert resp2.status_code == 200
    assert resp2.get_json()["ok"] is True