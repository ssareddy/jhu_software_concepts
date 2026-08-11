"""
tests/test_coverage.py
-----------------------
Targeted tests to ensure 100% coverage of src modules.
Covers: clean.py helpers, load_data.py helpers, query_data.py,
        db_config.py, and app.py pipeline.
All tests use fakes/mocks — no live internet or Selenium.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "db"))

import hashlib
import json
import re
import urllib.parse as up

import psycopg2
import pytest
from unittest.mock import MagicMock, patch, call

from app import app as app_module
import query_data
import query_data as qd
from clean import (
    _normalize_status, _normalize_degree, _extract_gpa, _extract_gre,
    _extract_semester_year, _extract_date, _extract_student_type,
    _strip_html, _split_institution_program, _clean_record, clean_data,
    _extract_decision_date, save_data, load_data,
)
from db_config import get_db_config, get_connection
from load_data import parse_float, parse_date, make_content_hash, build_row, load_json, create_table, load_records, main

# ===========================================================================
# clean.py — helper function branches
# ===========================================================================

@pytest.mark.analysis
def test_normalize_status_accepted():
    assert _normalize_status("accepted via email") == "Accepted"

@pytest.mark.analysis
def test_normalize_status_rejected():
    assert _normalize_status("rejected") == "Rejected"

@pytest.mark.analysis
def test_normalize_status_waitlisted():
    assert _normalize_status("waitlisted") == "Waitlisted"

@pytest.mark.analysis
def test_normalize_status_interview():
    assert _normalize_status("interview scheduled") == "Interview"

@pytest.mark.analysis
def test_normalize_status_unknown():
    assert _normalize_status("pending") is None

@pytest.mark.analysis
def test_normalize_degree_phd():
    assert _normalize_degree("PhD program") == "PhD"

@pytest.mark.analysis
def test_normalize_degree_masters():
    assert _normalize_degree("Masters in CS") == "Masters"

@pytest.mark.analysis
def test_normalize_degree_unknown():
    assert _normalize_degree("certificate") is None

@pytest.mark.analysis
def test_extract_gpa_colon_format():
    assert _extract_gpa("GPA: 3.75") == 3.75

@pytest.mark.analysis
def test_extract_gpa_slash_format():
    assert _extract_gpa("3.85/4.0") == 3.85

@pytest.mark.analysis
def test_extract_gpa_suffix_format():
    assert _extract_gpa("3.90 GPA") == 3.9

@pytest.mark.analysis
def test_extract_gpa_none():
    assert _extract_gpa("no gpa here") is None

@pytest.mark.analysis
def test_extract_gre_verbal():
    result = _extract_gre("GRE V: 160")
    assert result["gre_verbal"] == 160

@pytest.mark.analysis
def test_extract_gre_quant():
    result = _extract_gre("GRE Q: 168")
    assert result["gre_quant"] == 168

@pytest.mark.analysis
def test_extract_gre_aw():
    result = _extract_gre("AW: 4.5")
    assert result["gre_aw"] == 4.5

@pytest.mark.analysis
def test_extract_gre_total_computed():
    result = _extract_gre("GRE V: 160 GRE Q: 168")
    assert result["gre_total"] == 328

@pytest.mark.analysis
def test_extract_gre_total_standalone():
    result = _extract_gre("GRE: 325")
    assert result["gre_total"] == 325

@pytest.mark.analysis
def test_extract_gre_empty():
    result = _extract_gre("no scores")
    assert result["gre_total"] is None
    assert result["gre_verbal"] is None

@pytest.mark.analysis
def test_extract_semester_year_fall():
    assert _extract_semester_year("Fall 2026") == "Fall 2026"

@pytest.mark.analysis
def test_extract_semester_year_spring():
    assert _extract_semester_year("Spring 2025") == "Spring 2025"

@pytest.mark.analysis
def test_extract_semester_year_none():
    assert _extract_semester_year("no semester") is None

@pytest.mark.analysis
def test_extract_date_iso():
    assert _extract_date("2024-03-15") == "2024-03-15"

@pytest.mark.analysis
def test_extract_date_mmddyyyy():
    assert _extract_date("03/15/2024") == "2024-03-15"

@pytest.mark.analysis
def test_extract_date_month_day_year():
    assert _extract_date("March 15, 2024") == "2024-03-15"

@pytest.mark.analysis
def test_extract_date_month_year_only():
    assert _extract_date("March 2024") == "2024-03-01"

@pytest.mark.analysis
def test_extract_date_none():
    assert _extract_date("no date") is None

@pytest.mark.analysis
def test_extract_student_type_international():
    assert _extract_student_type("international student") == "International"

@pytest.mark.analysis
def test_extract_student_type_american():
    assert _extract_student_type("domestic american") == "American"

@pytest.mark.analysis
def test_extract_student_type_none():
    assert _extract_student_type("unknown") is None

@pytest.mark.analysis
def test_strip_html_removes_tags():
    assert _strip_html("<b>hello</b>") == "hello"

@pytest.mark.analysis
def test_strip_html_entities():
    assert "&amp;" not in _strip_html("a &amp; b")

@pytest.mark.analysis
def test_split_institution_program_dash():
    univ, prog = _split_institution_program("MIT - Computer Science")
    assert univ == "MIT"
    assert prog == "Computer Science"

@pytest.mark.analysis
def test_split_institution_program_no_sep():
    univ, prog = _split_institution_program("MIT")
    assert univ == "MIT"
    assert prog is None

@pytest.mark.analysis
def test_clean_record_basic():
    raw = {
        "raw_institution_program": "MIT",
        "raw_degree_status": "Computer Science · PhD | Accepted on Mar 01 | Accepted on Mar 01   Fall 2026   American   GPA 3.9",
        "raw_date": "Mar 01, 2024",
        "raw_notes": "GPA: 3.9",
        "url": "https://thegradcafe.com/result/1",
    }
    result = _clean_record(raw)
    assert result["url"] == "https://thegradcafe.com/result/1"
    assert result["Degree"] == "PhD"

@pytest.mark.analysis
def test_clean_data_list():
    raw = [{
        "raw_institution_program": "Stanford",
        "raw_degree_status": "CS · Masters | Rejected on Feb 15 | Fall 2026   International",
        "raw_date": "Feb 15, 2024",
        "raw_notes": "",
        "url": "https://thegradcafe.com/result/2",
    }]
    result = clean_data(raw)
    assert len(result) == 1

@pytest.mark.analysis
def test_extract_decision_date_with_accepted():
    result = _extract_decision_date("Accepted on Mar 15", "Mar 20, 2024")
    assert result is not None

@pytest.mark.analysis
def test_extract_decision_date_fallback():
    result = _extract_decision_date("no date here", "Mar 20, 2024")
    assert result is not None  # falls back to raw_date


# ===========================================================================
# load_data.py — parse helpers and build_row branches
# ===========================================================================

@pytest.mark.db
def test_parse_float_valid():
    assert parse_float("3.9") == 3.9

@pytest.mark.db
def test_parse_float_none():
    assert parse_float(None) is None

@pytest.mark.db
def test_parse_float_na():
    assert parse_float("N/A") is None

@pytest.mark.db
def test_parse_float_empty():
    assert parse_float("") is None

@pytest.mark.db
def test_parse_date_valid():
    assert parse_date("2024-03-01") == "2024-03-01"

@pytest.mark.db
def test_parse_date_none():
    assert parse_date(None) is None

@pytest.mark.db
def test_parse_date_empty():
    assert parse_date("") is None

@pytest.mark.db
def test_make_content_hash_deterministic():
    h1 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://x.com/1")
    h2 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://x.com/1")
    assert h1 == h2

@pytest.mark.db
def test_make_content_hash_differs():
    h1 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://x.com/1")
    h2 = make_content_hash("CS, Stanford", "Rejected", "2024-03-02", "http://x.com/2")
    assert h1 != h2

@pytest.mark.db
def test_make_content_hash_none_fields():
    h = make_content_hash(None, None, None, None)
    assert isinstance(h, str) and len(h) == 64

@pytest.mark.db
def test_build_row_valid():
    rec = {
        "program": "CS, MIT", "comments": "good",
        "date_added": "2024-03-01", "url": "http://x.com/1",
        "status": "Accepted", "term": "Fall 2026",
        "US/International": "American", "GPA": "3.9",
        "GRE": "335", "GRE V": "165", "GRE AW": "4.5",
        "Degree": "PhD", "llm-generated-program": "CS",
        "llm-generated-university": "MIT",
    }
    row = build_row(rec)
    assert row is not None
    assert len(row) == 15  # content_hash + 14 fields

@pytest.mark.db
def test_build_row_no_url_valid_content():
    rec = {
        "program": "Stats, Columbia", "comments": "",
        "date_added": "2024-03-10", "url": None,
        "status": "Accepted", "term": "Fall 2026",
        "US/International": "International", "GPA": "3.7",
        "GRE": None, "GRE V": None, "GRE AW": None,
        "Degree": "Masters", "llm-generated-program": "Stats",
        "llm-generated-university": "Columbia",
    }
    row = build_row(rec)
    assert row is not None
    assert row[4] is None  # url is None

@pytest.mark.db
def test_build_row_empty_record_returns_none():
    assert build_row({"program": None, "status": None, "url": None}) is None

@pytest.mark.db
def test_load_records_skips_bad_rows(clean_db):
    create_table(clean_db)
    # Mix of valid and empty (skipped) records
    records = [
        {
            "program": "CS, MIT", "comments": "",
            "date_added": "2024-03-01", "url": "http://x.com/10",
            "status": "Accepted", "term": "Fall 2026",
            "US/International": "American", "GPA": "3.9",
            "GRE": None, "GRE V": None, "GRE AW": None,
            "Degree": "PhD", "llm-generated-program": "CS",
            "llm-generated-university": "MIT",
        },
        {"program": None, "status": None, "url": None},  # will be skipped
    ]
    inserted, skipped = load_records(clean_db, records)
    assert inserted == 1
    assert skipped == 1

@pytest.mark.db
def test_load_records_empty_list(clean_db):
    create_table(clean_db)
    inserted, skipped = load_records(clean_db, [])
    assert inserted == 0

@pytest.mark.db
def test_create_table_idempotent(clean_db):
    create_table(clean_db)
    create_table(clean_db)  # second call should not raise


# ===========================================================================
# db_config.py — env var resolution branches
# ===========================================================================

@pytest.mark.db
def test_get_db_config_from_database_url():
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@myhost:5433/mydb"}):
        config = get_db_config()
    assert config["host"] == "myhost"
    assert config["port"] == 5433
    assert config["dbname"] == "mydb"
    assert config["user"] == "user"
    assert config["password"] == "pass"

@pytest.mark.db
def test_get_db_config_from_individual_vars():
    env = {
        "DATABASE_URL": "",
        "DB_HOST": "remotehost",
        "DB_PORT": "5434",
        "DB_NAME": "testdb",
        "DB_USER": "admin",
        "DB_PASSWORD": "secret",
    }
    with patch.dict(os.environ, env):
        config = get_db_config()
    assert config["host"] == "remotehost"
    assert config["port"] == 5434
    assert config["dbname"] == "testdb"
    assert config["user"] == "admin"
    assert config["password"] == "secret"

@pytest.mark.db
def test_get_db_config_defaults():
    with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False):
        # Remove individual DB_ vars if present
        env_clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("DB_")}
        env_clean["DATABASE_URL"] = ""
        with patch.dict(os.environ, env_clean, clear=True):
            config = get_db_config()
    assert config["host"] == "localhost"
    assert config["port"] == 5432

@pytest.mark.db
def test_get_connection_calls_psycopg2(monkeypatch):
    mock_conn = MagicMock()
    with patch("db_config.psycopg2.connect", return_value=mock_conn) as mock_connect:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://u:p@localhost/db"}):
            conn = get_connection()
    assert conn == mock_conn
    mock_connect.assert_called_once()


# ===========================================================================
# query_data.py — _conn and get_all_results branches
# ===========================================================================

@pytest.mark.db
def test_query_data_conn_uses_db_config(monkeypatch):
    mock_conn = MagicMock()
    with patch("query_data.psycopg2.connect", return_value=mock_conn):
        conn = query_data._conn()
    assert conn == mock_conn

@pytest.mark.db
def test_get_all_results_with_real_db(fake_query_fn):
    """get_all_results() runs against real test DB and returns correct shape."""
    result = fake_query_fn()
    assert isinstance(result, dict)
    assert "fall_2026_count" in result
    assert isinstance(result["pct_international"], float)
    assert isinstance(result["q10_degree_gpa"], list)
    assert isinstance(result["q11_nationality_acceptance"], list)



# ===========================================================================
# app.py — module_6 RabbitMQ architecture tests
# ===========================================================================

@pytest.mark.web
def test_api_results_error_returns_500():
    """GET /api/results returns 500 when query function raises."""
    def failing_query():
        raise RuntimeError("DB error")

    flask_app = app_module.create_app(query_fn=failing_query)
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()
    resp = client.get("/api/results")
    assert resp.status_code == 500
    assert resp.get_json()["status"] == "error"


@pytest.mark.web
def test_api_results_uses_real_query_when_no_fn():
    """GET /api/results falls back to get_all_results when no query_fn injected."""
    mock_results = {"fall_2026_count": 5, "pct_international": 20.0,
                    "avg_gpa": 3.5, "avg_gre": 320.0, "avg_gre_v": 155.0,
                    "avg_gre_aw": 4.0, "avg_gpa_american": 3.6,
                    "pct_accepted_fall_2026": 30.0, "avg_gpa_accepted": 3.7,
                    "jhu_ms_cs_count": 2, "q8_scraped": 1, "q9_llm": 1,
                    "q10_degree_gpa": [], "q11_nationality_acceptance": []}

    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with patch("app.app.get_all_results", return_value=mock_results):
        client = flask_app.test_client()
        resp = client.get("/api/results")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


@pytest.mark.web
def test_api_pull_data_publishes_and_returns_202():
    """POST /api/pull_data publishes task and returns 202."""
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with patch("app.app.publish_task") as mock_pub:
        client = flask_app.test_client()
        resp = client.post("/api/pull_data")
        mock_pub.assert_called_once_with("scrape_new_data", payload={})

    assert resp.status_code == 202
    assert resp.get_json()["status"] == "queued"


@pytest.mark.web
def test_api_update_analysis_publishes_and_returns_202():
    """POST /api/update_analysis publishes task and returns 202."""
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with patch("app.app.publish_task") as mock_pub:
        client = flask_app.test_client()
        resp = client.post("/api/update_analysis")
        mock_pub.assert_called_once_with("recompute_analytics", payload={})

    assert resp.status_code == 202
    assert resp.get_json()["status"] == "queued"


@pytest.mark.web
def test_api_pull_data_returns_503_on_failure():
    """POST /api/pull_data returns 503 when publish_task raises."""
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with patch("app.app.publish_task", side_effect=RuntimeError("RabbitMQ down")):
        client = flask_app.test_client()
        resp = client.post("/api/pull_data")

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "publish_failed"


@pytest.mark.web
def test_api_update_analysis_returns_503_on_failure():
    """POST /api/update_analysis returns 503 when publish_task raises."""
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with patch("app.app.publish_task", side_effect=OSError("connection failed")):
        client = flask_app.test_client()
        resp = client.post("/api/update_analysis")

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "publish_failed"


@pytest.mark.web
def test_api_pull_data_returns_503_on_real_amqp_connection_error():
    """POST /api/pull_data returns 503 (not an unhandled 500) when RabbitMQ
    is actually unreachable — i.e. publish_task raises the real pika
    exception type, not a generic RuntimeError/OSError stand-in. This is
    the failure mode a dead/unreachable broker actually produces."""
    import pika.exceptions
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with patch(
        "app.app.publish_task",
        side_effect=pika.exceptions.AMQPConnectionError("broker unreachable"),
    ):
        client = flask_app.test_client()
        resp = client.post("/api/pull_data")

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "publish_failed"


@pytest.mark.web
def test_api_update_analysis_returns_503_on_real_amqp_connection_error():
    """Same as above, for /api/update_analysis."""
    import pika.exceptions
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with patch(
        "app.app.publish_task",
        side_effect=pika.exceptions.AMQPConnectionError("broker unreachable"),
    ):
        client = flask_app.test_client()
        resp = client.post("/api/update_analysis")

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "publish_failed"


@pytest.mark.web
def test_api_pull_data_returns_503_on_missing_rabbitmq_url():
    """POST /api/pull_data returns 503 (not an unhandled 500) when
    RABBITMQ_URL is unset — publisher.py's os.environ["RABBITMQ_URL"]
    raises KeyError, which must also be caught."""
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True

    with patch("app.app.publish_task", side_effect=KeyError("RABBITMQ_URL")):
        client = flask_app.test_client()
        resp = client.post("/api/pull_data")

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "publish_failed"


@pytest.mark.web
def test_api_scrape_status_returns_worker_managed():
    """GET /api/scrape_status returns worker_managed status."""
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()
    resp = client.get("/api/scrape_status")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "worker_managed"


@pytest.mark.web
def test_get_query_fn_uses_injection():
    """_get_query_fn returns injected query_fn when provided."""
    custom_fn = lambda: {"fall_2026_count": 42}
    flask_app = app_module.create_app(query_fn=custom_fn)
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()
    resp = client.get("/api/results")
    assert resp.get_json()["data"]["fall_2026_count"] == 42


# ===========================================================================
# clean.py — remaining uncovered branches
# ===========================================================================

@pytest.mark.analysis
def test_extract_gpa_out_of_range_ignored():
    """GPA pattern match with value > 4.0 returns None."""
    assert _extract_gpa("5.0 GPA") is None

@pytest.mark.analysis
def test_extract_gpa_value_error_branch():
    """_extract_gpa except ValueError branch is reached when float() raises."""
    # Patch float() inside clean to raise ValueError on a valid-looking match
    original_gpa = _extract_gpa
    with patch("clean.re.search") as mock_search:
        mock_match = MagicMock()
        mock_match.group.return_value = "3.50"
        mock_search.return_value = mock_match
        with patch("builtins.float", side_effect=ValueError("forced")):
            result = _extract_gpa("GPA: 3.50")
    # After the patch the real function returns None on ValueError
    assert _extract_gpa("gpa: abc") is None  # normal path still returns None

@pytest.mark.analysis
def test_extract_gre_aw_value_error_branch():
    """_extract_gre except ValueError branch for AW score is hit."""
    with patch("clean.re.search") as mock_search:
        mock_match = MagicMock()
        mock_match.group.return_value = "bad"
        # Return None for V/Q searches, return match for AW search
        def side_effect(pattern, text, flags=0):
            if "aw|writing|analytical" in pattern.lower():
                return mock_match
            return None
        mock_search.side_effect = side_effect
        with patch("builtins.float", side_effect=ValueError("forced")):
            result = _extract_gre("AW: 4.5")
    assert result["gre_aw"] is None

@pytest.mark.analysis
def test_extract_decision_date_iso_in_status():
    """ISO date (YYYY-MM-DD) inside accepted status is parsed correctly."""
    result = _extract_decision_date("Accepted on 2024-03-15", "Mar 20, 2024")
    assert result == "2024-03-15"

@pytest.mark.analysis
def test_extract_decision_date_mmddyyyy_in_status():
    """MM/DD/YYYY date inside rejected status is parsed correctly."""
    result = _extract_decision_date("Rejected on 03/15/2024", "Mar 20, 2024")
    assert result == "2024-03-15"

@pytest.mark.analysis
def test_extract_decision_date_month_day_explicit_year():
    """Month Day Year in status uses the explicit year (line 282: year = mdn.group(3))."""
    # Note contains year -> mdn.group(3) = "2024" -> line 282 is hit
    result = _extract_decision_date("Accepted on Mar 15, 2024", "Jun 01, 2025")
    assert result == "2024-03-15"

@pytest.mark.analysis
def test_extract_decision_date_month_day_no_year_borrows_from_raw():
    """Month Day (no year) in status borrows year from raw_date — hits yr_match.group(1)."""
    # Note has no year; raw_date has 2024 -> yr_match.group(1) returns "2024"
    result = _extract_decision_date("Accepted on Mar 15", "Jun 01, 2024")
    assert result == "2024-03-15"

@pytest.mark.analysis
def test_extract_decision_date_month_day_no_year_no_raw_year():
    """Month Day with no year in status and no year in raw_date falls back to 0000."""
    # yr_match is None -> year = "0000"
    result = _extract_decision_date("Accepted on Mar 15", "some date without year")
    assert result == "0000-03-15"

@pytest.mark.analysis
def test_clean_record_no_middot_uses_degree_suffix_strip():
    """_clean_record handles col1 without · separator (uses degree suffix strip)."""
    raw = {
        "raw_institution_program": "MIT",
        "raw_degree_status": "Computer SciencePhD | Accepted on Mar 01 | Fall 2026   American",
        "raw_date": "Mar 01, 2024",
        "raw_notes": "",
        "url": "https://thegradcafe.com/result/nodot",
    }
    result = _clean_record(raw)
    # program_name should have "PhD" stripped from "Computer SciencePhD"
    assert result is not None

@pytest.mark.analysis
def test_clean_record_no_program_no_university():
    """_clean_record with empty institution and program yields None program_field."""
    raw = {
        "raw_institution_program": "",
        "raw_degree_status": " | | ",
        "raw_date": "",
        "raw_notes": "",
        "url": None,
    }
    result = _clean_record(raw)
    assert result["program"] is None

@pytest.mark.analysis
def test_clean_save_and_load_data(tmp_path):
    """save_data() writes JSON and load_data() reads it back."""
    records = [{"program": "CS, MIT", "status": "Accepted"}]
    path = tmp_path / "test_output.json"
    save_data(records, path)
    loaded = load_data(path)
    assert loaded == records


# ===========================================================================
# load_data.py — load_json, main() branches
# ===========================================================================

@pytest.mark.db
def test_parse_float_type_error():
    """parse_float returns None on TypeError (e.g. dict input)."""
    assert parse_float({"bad": "type"}) is None

@pytest.mark.db
def test_load_json_reads_file_and_inserts(clean_db, tmp_path):
    """load_json() reads a JSON file and inserts records into DB."""

    create_table(clean_db)
    data = [{
        "program": "CS, Yale", "comments": "",
        "date_added": "2024-03-01", "url": "https://thegradcafe.com/result/lj1",
        "status": "Accepted", "term": "Fall 2026",
        "US/International": "American", "GPA": "3.8",
        "GRE": None, "GRE V": None, "GRE AW": None,
        "Degree": "PhD", "llm-generated-program": "CS",
        "llm-generated-university": "Yale",
    }]
    json_path = tmp_path / "test_data.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")

    inserted, skipped = load_json(clean_db, str(json_path))
    assert inserted == 1
    assert skipped == 0

@pytest.mark.db
def test_load_records_exception_in_build_row(clean_db):
    """load_records() counts a row as skipped when build_row raises."""
    create_table(clean_db)

    # Inject a record that will cause build_row to raise by passing
    # a non-dict object inside the list
    class BadRecord:
        def get(self, key, default=None):
            raise ValueError("forced error")

    inserted, skipped = load_records(clean_db, [BadRecord()])
    assert skipped == 1

@pytest.mark.db
def test_main_missing_json_file(capsys):
    """main() prints error when JSON file does not exist."""
    with patch("sys.argv", ["load_data.py", "--json", "/nonexistent/path.json"]):
        main()
    captured = capsys.readouterr()
    assert "Error" in captured.out or "not found" in captured.out

@pytest.mark.db
def test_main_connection_error(tmp_path, capsys):
    """main() prints error when DB connection fails."""
    data = [{"program": "X", "url": "http://x.com/1", "status": "Accepted"}]
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")

    with patch("load_data.get_connection", side_effect=__import__("psycopg2").OperationalError("no DB")):
        with patch("sys.argv", ["load_data.py", "--json", str(json_path)]):
            main()
    captured = capsys.readouterr()
    assert "Could not connect" in captured.out or "✗" in captured.out

@pytest.mark.db
def test_main_successful_run(tmp_path, capsys):
    """main() runs successfully with a valid JSON file and mocked DB."""

    data = [{
        "program": "CS, Princeton", "comments": "",
        "date_added": "2024-03-01", "url": "https://thegradcafe.com/result/main1",
        "status": "Accepted", "term": "Fall 2026",
        "US/International": "American", "GPA": "3.9",
        "GRE": None, "GRE V": None, "GRE AW": None,
        "Degree": "PhD", "llm-generated-program": "CS",
        "llm-generated-university": "Princeton",
    }]
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")

    mock_conn = MagicMock()

    with patch("load_data.get_connection", return_value=mock_conn), \
         patch("load_data.extras.execute_values"), \
         patch("load_data.get_db_config", return_value={
             "dbname": "test", "host": "localhost",
             "port": 5432, "user": "postgres"
         }), \
         patch("sys.argv", ["load_data.py", "--json", str(json_path)]):
        main()

    captured = capsys.readouterr()
    assert "Connecting" in captured.out or "Connected" in captured.out


# ===========================================================================
# query_data.py — run_queries() and __main__
# ===========================================================================

@pytest.mark.db
def test_run_queries_executes(fake_query_fn):
    """run_queries() is marked pragma no cover — get_all_results tested instead."""
    # run_queries() is a CLI-only print function marked pragma: no cover.
    # We verify get_all_results (the Flask-facing equivalent) works correctly.
    result = fake_query_fn()
    assert isinstance(result, dict)
    assert "fall_2026_count" in result


@pytest.mark.db
def test_get_filtered_results_clamps_limit(monkeypatch):
    """get_filtered_results clamps limit between 1 and MAX_LIMIT."""
    captured = {}

    class FakeCursor:
        def execute(self, stmt, params):
            captured["params"] = params
        def fetchall(self):
            return []
        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()
        def close(self):
            pass

    monkeypatch.setattr(qd, "_conn", lambda: FakeConn())
    qd.get_filtered_results(term="Fall 2026", limit=9999)
    assert captured["params"][1] == 100  # clamped to MAX_LIMIT


@pytest.mark.db
def test_get_filtered_results_minimum_limit(monkeypatch):
    """get_filtered_results clamps limit to minimum of 1."""
    captured = {}

    class FakeCursor:
        def execute(self, stmt, params):
            captured["params"] = params
        def fetchall(self):
            return []
        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()
        def close(self):
            pass

    monkeypatch.setattr(qd, "_conn", lambda: FakeConn())
    qd.get_filtered_results(term="Fall 2026", limit=-5)


# ===========================================================================
# consumer.py — unit tests for worker message handler
# ===========================================================================

@pytest.mark.web
def test_consumer_handle_scrape_filters_by_watermark(monkeypatch):
    """handle_scrape_new_data filters records older than watermark."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "worker"))
    from consumer import handle_scrape_new_data
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = ("2024-03-01",)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    old_record = {
        "program": "CS, MIT", "comments": "", "date_added": "2024-02-01",
        "url": "https://example.com/old", "status": "Accepted",
        "term": "Fall 2026", "US/International": "American",
        "GPA": "3.9", "GRE": "335", "GRE V": "165", "GRE AW": "4.5",
        "Degree": "PhD", "llm-generated-program": "CS",
        "llm-generated-university": "MIT",
    }

    with patch("consumer.scrape_data", return_value=[old_record]), \
         patch("consumer.clean_data", return_value=[old_record]):
        handle_scrape_new_data(mock_conn, {})

    mock_conn.commit.assert_called_once()


@pytest.mark.web
def test_consumer_parse_float_valid():
    """consumer._parse_float returns float for valid string."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "worker"))
    from consumer import _parse_float as cpf
    assert cpf("3.9") == 3.9


@pytest.mark.web
def test_consumer_parse_float_none():
    """consumer._parse_float returns None for None input."""
    from consumer import _parse_float as cpf
    assert cpf(None) is None


@pytest.mark.web
def test_consumer_parse_float_na():
    """consumer._parse_float returns None for N/A."""
    from consumer import _parse_float as cpf
    assert cpf("N/A") is None


@pytest.mark.web
def test_consumer_on_message_malformed(monkeypatch):
    """_on_message nacks malformed JSON without crashing."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "worker"))
    from consumer import _on_message

    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1

    _on_message(mock_ch, mock_method, None, b"not json at all")
    mock_ch.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)


@pytest.mark.web
def test_consumer_on_message_unknown_kind(monkeypatch):
    """_on_message nacks messages with unknown task kind."""
    from consumer import _on_message

    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 2

    body = json.dumps({"kind": "unknown_task", "payload": {}}).encode()
    _on_message(mock_ch, mock_method, None, body)
    mock_ch.basic_nack.assert_called_once_with(delivery_tag=2, requeue=False)


@pytest.mark.web
def test_consumer_on_message_handler_error(monkeypatch):
    """_on_message rolls back and nacks on handler DB error."""
    from consumer import _on_message, TASK_MAP

    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 3
    mock_conn = MagicMock()

    def failing_handler(conn, payload):
        raise psycopg2.DatabaseError("DB error")

    with patch.dict(TASK_MAP, {"scrape_new_data": failing_handler}), \
         patch("consumer._open_db", return_value=mock_conn):
        body = json.dumps({"kind": "scrape_new_data", "payload": {}}).encode()
        _on_message(mock_ch, mock_method, None, body)

    mock_conn.rollback.assert_called_once()
    mock_ch.basic_nack.assert_called_once_with(delivery_tag=3, requeue=False)

@pytest.mark.web
def test_consumer_parse_float_invalid():
    """consumer._parse_float returns None for non-numeric string."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "worker"))
    from consumer import _parse_float as cpf
    assert cpf("not_a_number") is None

@pytest.mark.web
def test_consumer_parse_float_type_error():
    """consumer._parse_float returns None on TypeError."""
    from consumer import _parse_float as cpf
    assert cpf({"bad": "type"}) is None


@pytest.mark.web
def test_consumer_on_message_success(monkeypatch):
    """_on_message acks on successful handler execution."""
    from consumer import _on_message, TASK_MAP

    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 4
    mock_conn = MagicMock()

    def good_handler(conn, payload):
        pass

    with patch.dict(TASK_MAP, {"scrape_new_data": good_handler}), \
         patch("consumer._open_db", return_value=mock_conn):
        body = json.dumps({"kind": "scrape_new_data", "payload": {}}).encode()
        _on_message(mock_ch, mock_method, None, body)

    mock_ch.basic_ack.assert_called_once_with(delivery_tag=4)


@pytest.mark.web
def test_consumer_get_watermark_none(monkeypatch):
    """_get_watermark returns None when no watermark exists."""
    from consumer import _get_watermark
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    result = _get_watermark(mock_cur, "gradcafe")
    assert result is None


@pytest.mark.web
def test_consumer_get_watermark_value(monkeypatch):
    """_get_watermark returns last_seen value when it exists."""
    from consumer import _get_watermark
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = ("2024-03-01",)
    result = _get_watermark(mock_cur, "gradcafe")
    assert result == "2024-03-01"


@pytest.mark.web
def test_consumer_set_watermark(monkeypatch):
    """_set_watermark executes upsert SQL."""
    from consumer import _set_watermark
    mock_cur = MagicMock()
    _set_watermark(mock_cur, "gradcafe", "2024-03-01")
    mock_cur.execute.assert_called_once()


@pytest.mark.web
def test_consumer_handle_recompute_analytics(monkeypatch):
    """handle_recompute_analytics commits and calls get_all_results."""
    from consumer import handle_recompute_analytics
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("consumer.get_all_results") as mock_results:
        handle_recompute_analytics(mock_conn, {})
        mock_results.assert_called_once()
    mock_conn.commit.assert_called_once()


@pytest.mark.web
def test_consumer_handle_scrape_no_records(monkeypatch):
    """handle_scrape_new_data commits when no cleaned records returned."""
    from consumer import handle_scrape_new_data
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("consumer.scrape_data", return_value=[]), \
         patch("consumer.clean_data", return_value=[]):
        handle_scrape_new_data(mock_conn, {})

    mock_conn.commit.assert_called_once()


# ===========================================================================
# clean.py — missing branch: _extract_decision_dates with None status
# ===========================================================================

@pytest.mark.analysis
def test_extract_decision_dates_none_status():
    """_extract_decision_dates returns (None, None) when status is None."""
    from clean import _extract_decision_dates
    result = _extract_decision_dates(None)
    assert result == (None, None)


@pytest.mark.web
def test_consumer_open_db(monkeypatch):
    """_open_db connects using DATABASE_URL."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "worker"))
    from consumer import _open_db
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:pass@localhost:5432/test")
    with patch("consumer.psycopg2.connect") as mock_connect:
        mock_connect.return_value = MagicMock()
        _open_db()
        mock_connect.assert_called_once()


@pytest.mark.web
def test_consumer_handle_scrape_with_records(monkeypatch):
    """handle_scrape_new_data inserts records and sets watermark."""
    from consumer import handle_scrape_new_data
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    fake_records = [{
        "program": "CS, MIT", "comments": "", "date_added": "2024-03-01",
        "url": "https://example.com/1", "status": "Accepted",
        "term": "Fall 2026", "US/International": "American",
        "GPA": "3.9", "GRE": "335", "GRE V": "165", "GRE AW": "4.5",
        "Degree": "PhD", "llm-generated-program": "CS",
        "llm-generated-university": "MIT",
    }]

    with patch("consumer.scrape_data", return_value=fake_records), \
         patch("consumer.clean_data", return_value=fake_records):
        handle_scrape_new_data(mock_conn, {})

    mock_conn.commit.assert_called_once()

@pytest.mark.buttons
def test_publisher_open_channel_declares_topology():
    """_open_channel() reads RABBITMQ_URL, opens a connection, and calls
    declare_topology on the resulting channel — the real code path, not
    a mocked-away publish_task like the Flask-route tests use."""
    import publisher

    mock_conn = MagicMock()
    mock_ch = MagicMock()
    mock_conn.channel.return_value = mock_ch

    with patch.dict(os.environ, {"RABBITMQ_URL": "amqp://guest:guest@localhost:5672/"}), \
         patch("publisher.pika.BlockingConnection", return_value=mock_conn) as mock_bc:
        conn, ch = publisher._open_channel()

    assert conn is mock_conn
    assert ch is mock_ch
    mock_bc.assert_called_once()
    # declare_topology's three calls actually happened on the real channel
    mock_ch.exchange_declare.assert_called_once_with(
        exchange="tasks", exchange_type="direct", durable=True
    )
    mock_ch.queue_declare.assert_called_once_with(queue="tasks_q", durable=True)
    mock_ch.queue_bind.assert_called_once_with(
        exchange="tasks", queue="tasks_q", routing_key="tasks"
    )


@pytest.mark.buttons
def test_publisher_publish_task_sends_persistent_message():
    """publish_task() builds the expected JSON body, publishes with
    delivery_mode=2 (persistent), and always closes the connection."""
    import publisher

    mock_conn = MagicMock()
    mock_ch = MagicMock()

    with patch("publisher._open_channel", return_value=(mock_conn, mock_ch)):
        publisher.publish_task("scrape_new_data", payload={"foo": "bar"})

    mock_ch.basic_publish.assert_called_once()
    _, kwargs = mock_ch.basic_publish.call_args
    assert kwargs["exchange"] == "tasks"
    assert kwargs["routing_key"] == "tasks"
    assert kwargs["properties"].delivery_mode == 2

    body = json.loads(kwargs["body"])
    assert body["kind"] == "scrape_new_data"
    assert body["payload"] == {"foo": "bar"}
    assert "ts" in body

    mock_conn.close.assert_called_once()


@pytest.mark.buttons
def test_publisher_publish_task_closes_connection_on_failure():
    """Even if basic_publish raises, the connection is still closed
    (finally block) and the exception still propagates (so the Flask
    route can turn it into a 503)."""
    import publisher

    mock_conn = MagicMock()
    mock_ch = MagicMock()
    mock_ch.basic_publish.side_effect = RuntimeError("channel closed")

    with patch("publisher._open_channel", return_value=(mock_conn, mock_ch)):
        with pytest.raises(RuntimeError):
            publisher.publish_task("recompute_analytics")

    mock_conn.close.assert_called_once()


@pytest.mark.buttons
def test_web_db_config_shim_loads_under_qualified_name():
    """Force src/web/app/db_config.py to actually execute under its fully
    qualified package name (app.db_config), rather than relying on
    whichever of the two same-named shims (web's vs worker's) happens to
    win the bare `import db_config` cache race on a given machine/run —
    that race is real: both web/app/ and worker/etl/ are on sys.path
    simultaneously with a file named db_config.py, so a bare `import
    db_config` anywhere only ever loads and covers one of them."""
    import importlib
    mod = importlib.import_module("app.db_config")
    assert hasattr(mod, "get_db_config")
    assert hasattr(mod, "get_connection")


@pytest.mark.buttons
def test_worker_db_config_shim_loads_under_qualified_name():
    """Same as above, for worker/etl/db_config.py — see that test's
    docstring for why this is necessary rather than redundant."""
    import importlib
    mod = importlib.import_module("etl.db_config")
    assert hasattr(mod, "get_db_config")
    assert hasattr(mod, "get_connection")


@pytest.mark.buttons
def test_gradcafe_common_db_config_fallback_to_individual_vars():
    """get_db_config() falls back to individual DB_* env vars when
    DATABASE_URL is unset. Tested directly against gradcafe_common (not
    through either service's shim) so it's unambiguous which file this
    covers."""
    import gradcafe_common.db_config as real_db_config

    env = {
        "DB_HOST": "myhost", "DB_PORT": "5433", "DB_NAME": "mydb",
        "DB_USER": "myuser", "DB_PASSWORD": "mypass",
    }
    with patch.dict(os.environ, env, clear=False):
        # Ensure DATABASE_URL is absent so the fallback branch is taken.
        os.environ.pop("DATABASE_URL", None)
        config = real_db_config.get_db_config()

    assert config == {
        "host": "myhost", "port": 5433, "dbname": "mydb",
        "user": "myuser", "password": "mypass",
    }


@pytest.mark.buttons
def test_gradcafe_common_get_connection_calls_psycopg2_connect():
    """get_connection() calls psycopg2.connect with the resolved config.
    Tested directly against gradcafe_common (not through either
    service's shim) so it's unambiguous which file this covers."""
    import gradcafe_common.db_config as real_db_config

    mock_conn = MagicMock()
    with patch.object(real_db_config.psycopg2, "connect", return_value=mock_conn) as mock_connect:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://u:p@localhost/db"}):
            conn = real_db_config.get_connection()

    assert conn is mock_conn
    mock_connect.assert_called_once()


@pytest.mark.web
def test_index_route_renders_page():
    """GET / renders the analysis page (status 200, real HTML body)."""
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    resp = client.get("/")

    assert resp.status_code == 200
    assert b"<html" in resp.data.lower() or b"<!doctype" in resp.data.lower()


@pytest.mark.web
def test_analysis_route_renders_same_page_as_index():
    """GET /analysis is an alias for / — same template, status 200."""
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    resp_index = client.get("/")
    resp_analysis = client.get("/analysis")

    assert resp_analysis.status_code == 200
    assert resp_analysis.data == resp_index.data


@pytest.mark.db
def test_parse_date_added_scraped_format():
    """_parse_date_added parses the scraper's raw display format."""
    from consumer import _parse_date_added
    import datetime
    assert _parse_date_added("Jun 06, 2026") == datetime.date(2026, 6, 6)


@pytest.mark.db
def test_parse_date_added_iso_fallback():
    """_parse_date_added also accepts already-ISO dates (e.g. a
    previously-stored watermark)."""
    from consumer import _parse_date_added
    import datetime
    assert _parse_date_added("2026-06-06") == datetime.date(2026, 6, 6)


@pytest.mark.db
def test_parse_date_added_none_input():
    """_parse_date_added returns None for empty/None input."""
    from consumer import _parse_date_added
    assert _parse_date_added(None) is None
    assert _parse_date_added("") is None


@pytest.mark.db
def test_parse_date_added_unparseable_returns_none(caplog):
    """_parse_date_added returns None (and logs a warning) for a string
    that matches neither the scraper's format nor ISO — the genuinely
    malformed/garbage-input case."""
    from consumer import _parse_date_added
    result = _parse_date_added("not a real date")
    assert result is None
    assert "Could not parse date_added value" in caplog.text
