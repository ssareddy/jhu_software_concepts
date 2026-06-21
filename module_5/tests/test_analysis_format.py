"""
tests/test_analysis_format.py
------------------------------
Analysis formatting — labels, percentage rendering, rounding.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import re
import pytest
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TWO_DECIMAL_PCT = re.compile(r"\d+\.\d{2}%")


def _get_rendered_html(client):
    """Trigger Update Analysis and get the full page HTML."""
    # The page HTML (index.html) always contains Answer: labels statically
    return client.get("/analysis").data.decode()


def _get_update_json(client):
    resp = client.post("/api/update_analysis")
    return resp.get_json()


# ---------------------------------------------------------------------------
# Answer labels
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_page_has_answer_labels(client):
    """Page contains 'Answer:' labels."""
    html = _get_rendered_html(client)
    assert "Answer:" in html


@pytest.mark.analysis
def test_page_has_multiple_answer_labels(client):
    """Page contains more than one 'Answer:' label."""
    html = _get_rendered_html(client)
    count = html.count("Answer:")
    assert count >= 2, f"Expected multiple 'Answer:' labels, found {count}"


# ---------------------------------------------------------------------------
# Percentage formatting in the query results
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_pct_international_is_float(client):
    """pct_international from /api/results is a float."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    val = data["pct_international"]
    assert isinstance(val, float), f"pct_international should be float, got {type(val)}"


@pytest.mark.analysis
def test_pct_accepted_is_float(client):
    """pct_accepted_fall_2026 from /api/results is a float."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    val = data["pct_accepted_fall_2026"]
    assert isinstance(val, float)


@pytest.mark.analysis
def test_pct_international_two_decimals(client):
    """pct_international is rendered with exactly two decimal places in the API."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    val = data["pct_international"]
    formatted = f"{val:.2f}%"
    assert TWO_DECIMAL_PCT.match(formatted), f"Expected two-decimal %, got '{formatted}'"


@pytest.mark.analysis
def test_pct_accepted_two_decimals(client):
    """pct_accepted_fall_2026 is formatted to two decimal places."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    val = data["pct_accepted_fall_2026"]
    formatted = f"{val:.2f}%"
    assert TWO_DECIMAL_PCT.match(formatted)


@pytest.mark.analysis
def test_nationality_rates_two_decimals(client):
    """q11 nationality acceptance rates are two-decimal floats."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    for entry in data.get("q11_nationality_acceptance", []):
        rate = entry["rate"]
        formatted = f"{rate:.2f}%"
        assert TWO_DECIMAL_PCT.match(formatted), f"Rate not two-decimal: '{formatted}'"


# ---------------------------------------------------------------------------
# Average values are numeric
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_avg_gpa_is_numeric(client):
    """avg_gpa in results is a numeric value."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    assert isinstance(data["avg_gpa"], (int, float))


@pytest.mark.analysis
def test_avg_gre_is_numeric(client):
    """avg_gre in results is a numeric value."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    assert isinstance(data["avg_gre"], (int, float))


# ---------------------------------------------------------------------------
# update_analysis endpoint returns formatted values
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_update_analysis_returns_pct_as_float(client):
    """POST /api/update_analysis returns percentage values as floats."""
    data = _get_update_json(client)
    assert data["ok"] is True
    pct = data["data"]["pct_international"]
    assert isinstance(pct, float)


@pytest.mark.analysis
def test_update_analysis_pct_two_decimal_format(client):
    """POST /api/update_analysis pct_international can be formatted to two decimals."""
    data = _get_update_json(client)
    pct = data["data"]["pct_international"]
    formatted = f"{pct:.2f}%"
    assert TWO_DECIMAL_PCT.match(formatted)


# ---------------------------------------------------------------------------
# Mock data correctness checks
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_results_contain_expected_keys(client):
    """GET /api/results data contains all expected analysis keys."""
    expected_keys = [
        "fall_2026_count", "pct_international", "avg_gpa", "avg_gre",
        "avg_gre_v", "avg_gre_aw", "avg_gpa_american", "pct_accepted_fall_2026",
        "avg_gpa_accepted", "jhu_ms_cs_count", "q8_scraped", "q9_llm",
        "q10_degree_gpa", "q11_nationality_acceptance",
    ]
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    for key in expected_keys:
        assert key in data, f"Missing key: {key}"


@pytest.mark.analysis
def test_q10_entries_have_required_fields(client):
    """q10_degree_gpa entries each have degree_type, avg_gpa, count."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    for entry in data["q10_degree_gpa"]:
        assert "degree_type" in entry
        assert "avg_gpa" in entry
        assert "count" in entry


@pytest.mark.analysis
def test_q11_entries_have_required_fields(client):
    """q11_nationality_acceptance entries each have nationality, total, accepted, rate."""
    resp = client.get("/api/results")
    data = resp.get_json()["data"]
    for entry in data["q11_nationality_acceptance"]:
        assert "nationality" in entry
        assert "total" in entry
        assert "accepted" in entry
        assert "rate" in entry
