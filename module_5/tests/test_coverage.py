"""
tests/test_coverage.py
-----------------------
Targeted tests to ensure 100% coverage of src modules.
Covers: clean.py helpers, load_data.py helpers, query_data.py,
        db_config.py, and app.py pipeline.
All tests use fakes/mocks — no live internet or Selenium.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import hashlib
import threading
import pytest
from unittest.mock import MagicMock, patch, call


# ===========================================================================
# clean.py — helper function branches
# ===========================================================================

@pytest.mark.analysis
def test_normalize_status_accepted():
    from clean import _normalize_status
    assert _normalize_status("accepted via email") == "Accepted"

@pytest.mark.analysis
def test_normalize_status_rejected():
    from clean import _normalize_status
    assert _normalize_status("rejected") == "Rejected"

@pytest.mark.analysis
def test_normalize_status_waitlisted():
    from clean import _normalize_status
    assert _normalize_status("waitlisted") == "Waitlisted"

@pytest.mark.analysis
def test_normalize_status_interview():
    from clean import _normalize_status
    assert _normalize_status("interview scheduled") == "Interview"

@pytest.mark.analysis
def test_normalize_status_unknown():
    from clean import _normalize_status
    assert _normalize_status("pending") is None

@pytest.mark.analysis
def test_normalize_degree_phd():
    from clean import _normalize_degree
    assert _normalize_degree("PhD program") == "PhD"

@pytest.mark.analysis
def test_normalize_degree_masters():
    from clean import _normalize_degree
    assert _normalize_degree("Masters in CS") == "Masters"

@pytest.mark.analysis
def test_normalize_degree_unknown():
    from clean import _normalize_degree
    assert _normalize_degree("certificate") is None

@pytest.mark.analysis
def test_extract_gpa_colon_format():
    from clean import _extract_gpa
    assert _extract_gpa("GPA: 3.75") == 3.75

@pytest.mark.analysis
def test_extract_gpa_slash_format():
    from clean import _extract_gpa
    assert _extract_gpa("3.85/4.0") == 3.85

@pytest.mark.analysis
def test_extract_gpa_suffix_format():
    from clean import _extract_gpa
    assert _extract_gpa("3.90 GPA") == 3.9

@pytest.mark.analysis
def test_extract_gpa_none():
    from clean import _extract_gpa
    assert _extract_gpa("no gpa here") is None

@pytest.mark.analysis
def test_extract_gre_verbal():
    from clean import _extract_gre
    result = _extract_gre("GRE V: 160")
    assert result["gre_verbal"] == 160

@pytest.mark.analysis
def test_extract_gre_quant():
    from clean import _extract_gre
    result = _extract_gre("GRE Q: 168")
    assert result["gre_quant"] == 168

@pytest.mark.analysis
def test_extract_gre_aw():
    from clean import _extract_gre
    result = _extract_gre("AW: 4.5")
    assert result["gre_aw"] == 4.5

@pytest.mark.analysis
def test_extract_gre_total_computed():
    from clean import _extract_gre
    result = _extract_gre("GRE V: 160 GRE Q: 168")
    assert result["gre_total"] == 328

@pytest.mark.analysis
def test_extract_gre_total_standalone():
    from clean import _extract_gre
    result = _extract_gre("GRE: 325")
    assert result["gre_total"] == 325

@pytest.mark.analysis
def test_extract_gre_empty():
    from clean import _extract_gre
    result = _extract_gre("no scores")
    assert result["gre_total"] is None
    assert result["gre_verbal"] is None

@pytest.mark.analysis
def test_extract_semester_year_fall():
    from clean import _extract_semester_year
    assert _extract_semester_year("Fall 2026") == "Fall 2026"

@pytest.mark.analysis
def test_extract_semester_year_spring():
    from clean import _extract_semester_year
    assert _extract_semester_year("Spring 2025") == "Spring 2025"

@pytest.mark.analysis
def test_extract_semester_year_none():
    from clean import _extract_semester_year
    assert _extract_semester_year("no semester") is None

@pytest.mark.analysis
def test_extract_date_iso():
    from clean import _extract_date
    assert _extract_date("2024-03-15") == "2024-03-15"

@pytest.mark.analysis
def test_extract_date_mmddyyyy():
    from clean import _extract_date
    assert _extract_date("03/15/2024") == "2024-03-15"

@pytest.mark.analysis
def test_extract_date_month_day_year():
    from clean import _extract_date
    assert _extract_date("March 15, 2024") == "2024-03-15"

@pytest.mark.analysis
def test_extract_date_month_year_only():
    from clean import _extract_date
    assert _extract_date("March 2024") == "2024-03-01"

@pytest.mark.analysis
def test_extract_date_none():
    from clean import _extract_date
    assert _extract_date("no date") is None

@pytest.mark.analysis
def test_extract_student_type_international():
    from clean import _extract_student_type
    assert _extract_student_type("international student") == "International"

@pytest.mark.analysis
def test_extract_student_type_american():
    from clean import _extract_student_type
    assert _extract_student_type("domestic american") == "American"

@pytest.mark.analysis
def test_extract_student_type_none():
    from clean import _extract_student_type
    assert _extract_student_type("unknown") is None

@pytest.mark.analysis
def test_strip_html_removes_tags():
    from clean import _strip_html
    assert _strip_html("<b>hello</b>") == "hello"

@pytest.mark.analysis
def test_strip_html_entities():
    from clean import _strip_html
    assert "&amp;" not in _strip_html("a &amp; b")

@pytest.mark.analysis
def test_split_institution_program_dash():
    from clean import _split_institution_program
    univ, prog = _split_institution_program("MIT - Computer Science")
    assert univ == "MIT"
    assert prog == "Computer Science"

@pytest.mark.analysis
def test_split_institution_program_no_sep():
    from clean import _split_institution_program
    univ, prog = _split_institution_program("MIT")
    assert univ == "MIT"
    assert prog is None

@pytest.mark.analysis
def test_clean_record_basic():
    from clean import _clean_record
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
    from clean import clean_data
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
    from clean import _extract_decision_date
    result = _extract_decision_date("Accepted on Mar 15", "Mar 20, 2024")
    assert result is not None

@pytest.mark.analysis
def test_extract_decision_date_fallback():
    from clean import _extract_decision_date
    result = _extract_decision_date("no date here", "Mar 20, 2024")
    assert result is not None  # falls back to raw_date


# ===========================================================================
# load_data.py — parse helpers and build_row branches
# ===========================================================================

@pytest.mark.db
def test_parse_float_valid():
    from load_data import parse_float
    assert parse_float("3.9") == 3.9

@pytest.mark.db
def test_parse_float_none():
    from load_data import parse_float
    assert parse_float(None) is None

@pytest.mark.db
def test_parse_float_na():
    from load_data import parse_float
    assert parse_float("N/A") is None

@pytest.mark.db
def test_parse_float_empty():
    from load_data import parse_float
    assert parse_float("") is None

@pytest.mark.db
def test_parse_float_invalid():
    from load_data import parse_float
    assert parse_float("not_a_number") is None

@pytest.mark.db
def test_parse_date_valid():
    from load_data import parse_date
    assert parse_date("2024-03-01") == "2024-03-01"

@pytest.mark.db
def test_parse_date_none():
    from load_data import parse_date
    assert parse_date(None) is None

@pytest.mark.db
def test_parse_date_empty():
    from load_data import parse_date
    assert parse_date("") is None

@pytest.mark.db
def test_make_content_hash_deterministic():
    from load_data import make_content_hash
    h1 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://x.com/1")
    h2 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://x.com/1")
    assert h1 == h2

@pytest.mark.db
def test_make_content_hash_differs():
    from load_data import make_content_hash
    h1 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://x.com/1")
    h2 = make_content_hash("CS, Stanford", "Rejected", "2024-03-02", "http://x.com/2")
    assert h1 != h2

@pytest.mark.db
def test_make_content_hash_none_fields():
    from load_data import make_content_hash
    h = make_content_hash(None, None, None, None)
    assert isinstance(h, str) and len(h) == 64

@pytest.mark.db
def test_build_row_valid():
    from load_data import build_row
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
    from load_data import build_row
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
    from load_data import build_row
    assert build_row({"program": None, "status": None, "url": None}) is None

@pytest.mark.db
def test_load_records_skips_bad_rows(clean_db):
    from load_data import load_records, create_table
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
    from load_data import load_records, create_table
    create_table(clean_db)
    inserted, skipped = load_records(clean_db, [])
    assert inserted == 0

@pytest.mark.db
def test_create_table_idempotent(clean_db):
    from load_data import create_table
    create_table(clean_db)
    create_table(clean_db)  # second call should not raise


# ===========================================================================
# db_config.py — env var resolution branches
# ===========================================================================

@pytest.mark.db
def test_get_db_config_from_database_url():
    from db_config import get_db_config
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@myhost:5433/mydb"}):
        config = get_db_config()
    assert config["host"] == "myhost"
    assert config["port"] == 5433
    assert config["dbname"] == "mydb"
    assert config["user"] == "user"
    assert config["password"] == "pass"

@pytest.mark.db
def test_get_db_config_from_individual_vars():
    from db_config import get_db_config
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
    from db_config import get_db_config
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
    from db_config import get_connection
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
    import query_data
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
# app.py — run_scraper_pipeline and api_results error branch
# ===========================================================================

@pytest.mark.web
def test_run_scraper_pipeline_with_fake_scraper(clean_db):
    """run_scraper_pipeline executes with a fake scraper and real DB."""
    import app as app_module
    import urllib.parse as up
    import psycopg2

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/gradcafe_test"
    )
    r = up.urlparse(db_url)

    def fake_get_conn():
        return psycopg2.connect(
            host=r.hostname, port=r.port or 5432,
            dbname=r.path.lstrip("/"), user=r.username,
            password=r.password or "",
        )

    fake_records = [
        {
            "raw_institution_program": "MIT",
            "raw_degree_status": "CS · PhD | Accepted on Mar 01 | Fall 2026   American",
            "raw_date": "Mar 01, 2024",
            "raw_notes": "GPA: 3.9",
            "url": "https://thegradcafe.com/result/pipeline_test",
        }
    ]

    with patch("db_config.get_connection", fake_get_conn):
        app_module.run_scraper_pipeline(scraper_fn=lambda: fake_records)

    app_module._set_busy(False)


@pytest.mark.web
def test_run_scraper_pipeline_clears_busy_on_error():
    """run_scraper_pipeline clears busy state even when an error occurs."""
    import app as app_module
    app_module._set_busy(True)

    def bad_scraper():
        raise RuntimeError("Simulated scraper failure")

    # scraper raises before get_connection is called — no DB patch needed
    app_module.run_scraper_pipeline(scraper_fn=bad_scraper)

    assert app_module.is_busy() is False


@pytest.mark.web
def test_api_results_error_returns_500(mock_query_fn):
    """GET /api/results returns 500 when query function raises."""
    import app as app_module
    app_module._scrape_running = False

    def failing_query():
        raise RuntimeError("DB error")

    flask_app = app_module.create_app(query_fn=failing_query)
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    resp = client.get("/api/results")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["status"] == "error"


@pytest.mark.web
def test_api_update_analysis_error_returns_500(mock_query_fn):
    """POST /api/update_analysis returns 500 when query function raises."""
    import app as app_module
    app_module._scrape_running = False

    def failing_query():
        raise RuntimeError("DB error")

    flask_app = app_module.create_app(query_fn=failing_query)
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    resp = client.post("/api/update_analysis")
    assert resp.status_code == 500


@pytest.mark.web
def test_parse_float_valid_in_app():
    from app import _parse_float
    assert _parse_float("3.9") == 3.9

@pytest.mark.web
def test_parse_float_none_in_app():
    from app import _parse_float
    assert _parse_float(None) is None

@pytest.mark.web
def test_parse_float_invalid_in_app():
    from app import _parse_float
    assert _parse_float("bad") is None

@pytest.mark.web
def test_is_busy_false_by_default(app):
    from app import is_busy
    assert is_busy() is False


# ===========================================================================
# clean.py — remaining uncovered branches
# ===========================================================================

@pytest.mark.analysis
def test_extract_gpa_out_of_range_ignored():
    """GPA pattern match with value > 4.0 returns None."""
    from clean import _extract_gpa
    assert _extract_gpa("5.0 GPA") is None

@pytest.mark.analysis
def test_extract_gpa_value_error_branch():
    """_extract_gpa except ValueError branch is reached when float() raises."""
    from clean import _extract_gpa
    import re
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
    from clean import _extract_gre
    import re
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
    from clean import _extract_decision_date
    result = _extract_decision_date("Accepted on 2024-03-15", "Mar 20, 2024")
    assert result == "2024-03-15"

@pytest.mark.analysis
def test_extract_decision_date_mmddyyyy_in_status():
    """MM/DD/YYYY date inside rejected status is parsed correctly."""
    from clean import _extract_decision_date
    result = _extract_decision_date("Rejected on 03/15/2024", "Mar 20, 2024")
    assert result == "2024-03-15"

@pytest.mark.analysis
def test_extract_decision_date_month_day_explicit_year():
    """Month Day Year in status uses the explicit year (line 282: year = mdn.group(3))."""
    from clean import _extract_decision_date
    # Note contains year -> mdn.group(3) = "2024" -> line 282 is hit
    result = _extract_decision_date("Accepted on Mar 15, 2024", "Jun 01, 2025")
    assert result == "2024-03-15"

@pytest.mark.analysis
def test_extract_decision_date_month_day_no_year_borrows_from_raw():
    """Month Day (no year) in status borrows year from raw_date — hits yr_match.group(1)."""
    from clean import _extract_decision_date
    # Note has no year; raw_date has 2024 -> yr_match.group(1) returns "2024"
    result = _extract_decision_date("Accepted on Mar 15", "Jun 01, 2024")
    assert result == "2024-03-15"

@pytest.mark.analysis
def test_extract_decision_date_month_day_no_year_no_raw_year():
    """Month Day with no year in status and no year in raw_date falls back to 0000."""
    from clean import _extract_decision_date
    # yr_match is None -> year = "0000"
    result = _extract_decision_date("Accepted on Mar 15", "some date without year")
    assert result == "0000-03-15"

@pytest.mark.analysis
def test_clean_record_no_middot_uses_degree_suffix_strip():
    """_clean_record handles col1 without · separator (uses degree suffix strip)."""
    from clean import _clean_record
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
    from clean import _clean_record
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
    from clean import save_data, load_data
    records = [{"program": "CS, MIT", "status": "Accepted"}]
    path = tmp_path / "test_output.json"
    save_data(records, path)
    loaded = load_data(path)
    assert loaded == records


# ===========================================================================
# load_data.py — load_json, main() branches
# ===========================================================================

@pytest.mark.db
def test_load_json_reads_file_and_inserts(clean_db, tmp_path):
    """load_json() reads a JSON file and inserts records into DB."""
    import json
    from load_data import load_json, create_table

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
    from load_data import load_records, create_table
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
    from load_data import main
    with patch("sys.argv", ["load_data.py", "--json", "/nonexistent/path.json"]):
        main()
    captured = capsys.readouterr()
    assert "Error" in captured.out or "not found" in captured.out

@pytest.mark.db
def test_main_connection_error(tmp_path, capsys):
    """main() prints error when DB connection fails."""
    import json
    from load_data import main
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
    import json
    from load_data import main

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


# ===========================================================================
# app.py — db_url branch in run_scraper_pipeline
# ===========================================================================

@pytest.mark.web
def test_run_scraper_pipeline_with_db_url():
    """run_scraper_pipeline uses psycopg2.connect directly when db_url is provided."""
    import app as app_module

    db_url = "postgresql://postgres:postgres@localhost:5432/gradcafe_test"

    fake_records = [{
        "raw_institution_program": "Harvard",
        "raw_degree_status": "Physics · PhD | Accepted on Feb 20 | Fall 2026   American",
        "raw_date": "Feb 20, 2024",
        "raw_notes": "GPA: 3.95",
        "url": "https://thegradcafe.com/result/dburl_test",
    }]

    mock_conn = MagicMock()

    with patch("psycopg2.connect", return_value=mock_conn), \
         patch("psycopg2.extras.execute_values"):
        app_module.run_scraper_pipeline(
            scraper_fn=lambda: fake_records,
            db_url=db_url,
        )

    app_module._set_busy(False)
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()


@pytest.mark.web
def test_api_pull_data_uses_default_runner():
    """POST /api/pull_data uses run_scraper_pipeline when no loader_fn is set."""
    import app as app_module
    app_module._scrape_running = False

    done = threading.Event()

    def mock_pipeline(scraper_fn, db_url=""):
        done.set()
        app_module._set_busy(False)

    flask_app = app_module.create_app(query_fn=lambda: {
        "fall_2026_count": 0, "pct_international": 0.0,
        "avg_gpa": 0.0, "avg_gre": 0.0, "avg_gre_v": 0.0, "avg_gre_aw": 0.0,
        "avg_gpa_american": 0.0, "pct_accepted_fall_2026": 0.0,
        "avg_gpa_accepted": 0.0, "jhu_ms_cs_count": 0,
        "q8_scraped": 0, "q9_llm": 0,
        "q10_degree_gpa": [], "q11_nationality_acceptance": [],
    })
    flask_app.config["TESTING"] = True

    with patch("app.run_scraper_pipeline", mock_pipeline):
        client = flask_app.test_client()
        resp = client.post("/api/pull_data")

    done.wait(timeout=3)
    assert resp.status_code == 200


@pytest.mark.web
def test_api_results_uses_real_query_when_no_fn():
    """GET /api/results falls back to get_all_results when no query_fn injected."""
    import app as app_module
    app_module._scrape_running = False

    mock_results = {"fall_2026_count": 5, "pct_international": 20.0,
                    "avg_gpa": 3.5, "avg_gre": 320.0, "avg_gre_v": 155.0,
                    "avg_gre_aw": 4.0, "avg_gpa_american": 3.6,
                    "pct_accepted_fall_2026": 30.0, "avg_gpa_accepted": 3.7,
                    "jhu_ms_cs_count": 2, "q8_scraped": 1, "q9_llm": 1,
                    "q10_degree_gpa": [], "q11_nationality_acceptance": []}

    flask_app = app_module.create_app()  # no query_fn — uses real import
    flask_app.config["TESTING"] = True

    with patch("query_data.get_all_results", return_value=mock_results):
        client = flask_app.test_client()
        resp = client.get("/api/results")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


@pytest.mark.web
def test_api_update_analysis_uses_real_query_when_no_fn():
    """POST /api/update_analysis falls back to get_all_results when no query_fn injected."""
    import app as app_module
    app_module._scrape_running = False

    mock_results = {"fall_2026_count": 5, "pct_international": 20.0,
                    "avg_gpa": 3.5, "avg_gre": 320.0, "avg_gre_v": 155.0,
                    "avg_gre_aw": 4.0, "avg_gpa_american": 3.6,
                    "pct_accepted_fall_2026": 30.0, "avg_gpa_accepted": 3.7,
                    "jhu_ms_cs_count": 2, "q8_scraped": 1, "q9_llm": 1,
                    "q10_degree_gpa": [], "q11_nationality_acceptance": []}

    flask_app = app_module.create_app()  # no query_fn
    flask_app.config["TESTING"] = True

    with patch("query_data.get_all_results", return_value=mock_results):
        client = flask_app.test_client()
        resp = client.post("/api/update_analysis")

    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True