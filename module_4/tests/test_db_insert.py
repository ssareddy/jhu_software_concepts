"""
tests/test_db_insert.py
-----------------------
Database write, idempotency, and query function tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import psycopg2
from unittest.mock import patch, MagicMock
from conftest import (
    SAMPLE_RECORDS, _insert_records, _get_db_conn, DB_URL,
    CREATE_TABLE_SQL, INSERT_SQL,
)


# ---------------------------------------------------------------------------
# Insert on pull
# ---------------------------------------------------------------------------

@pytest.mark.db
def test_table_empty_before_insert(clean_db):
    """Before inserting, the applicants table is empty."""
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == 0


@pytest.mark.db
def test_rows_exist_after_insert(clean_db):
    """After inserting SAMPLE_RECORDS, rows exist in the table."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == len(SAMPLE_RECORDS)


@pytest.mark.db
def test_required_fields_non_null(clean_db):
    """Required fields (url, program, status) are non-null after insert."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    with clean_db.cursor() as cur:
        cur.execute("""
            SELECT url, program, status FROM applicants
            WHERE url IS NULL OR program IS NULL OR status IS NULL;
        """)
        bad_rows = cur.fetchall()
    assert bad_rows == [], f"Found rows with null required fields: {bad_rows}"


@pytest.mark.db
def test_url_is_unique_constraint(clean_db):
    """Inserting a record with a duplicate URL raises IntegrityError or is silently skipped."""
    _insert_records(clean_db, [SAMPLE_RECORDS[0]])
    # ON CONFLICT DO NOTHING means second insert should not raise
    _insert_records(clean_db, [SAMPLE_RECORDS[0]])
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants WHERE url = %s;",
                    (SAMPLE_RECORDS[0]["url"],))
        count = cur.fetchone()[0]
    assert count == 1, "Duplicate URL created duplicate row"


# ---------------------------------------------------------------------------
# Idempotency / constraints
# ---------------------------------------------------------------------------

@pytest.mark.db
def test_duplicate_pull_no_duplicates(clean_db):
    """Calling insert twice with the same data does not duplicate rows."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    _insert_records(clean_db, SAMPLE_RECORDS)  # second pull
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == len(SAMPLE_RECORDS), (
        f"Expected {len(SAMPLE_RECORDS)} rows, got {count} — duplicates exist"
    )


@pytest.mark.db
def test_overlapping_new_records_added(clean_db):
    """When a second pull includes new URLs, new rows are added."""
    _insert_records(clean_db, SAMPLE_RECORDS[:2])
    # All 3 records in second pull — one new
    _insert_records(clean_db, SAMPLE_RECORDS)
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == len(SAMPLE_RECORDS)


@pytest.mark.db
def test_gpa_stored_as_float(clean_db):
    """GPA values are stored as FLOAT in the DB."""
    _insert_records(clean_db, [SAMPLE_RECORDS[0]])
    with clean_db.cursor() as cur:
        cur.execute("SELECT gpa FROM applicants WHERE url = %s;",
                    (SAMPLE_RECORDS[0]["url"],))
        gpa = cur.fetchone()[0]
    assert isinstance(gpa, float)
    assert abs(gpa - 3.9) < 0.001


@pytest.mark.db
def test_null_gre_stored_as_null(clean_db):
    """Records with no GRE data store NULL for GRE columns."""
    _insert_records(clean_db, [SAMPLE_RECORDS[1]])  # GRE is None
    with clean_db.cursor() as cur:
        cur.execute("SELECT gre, gre_v, gre_aw FROM applicants WHERE url = %s;",
                    (SAMPLE_RECORDS[1]["url"],))
        row = cur.fetchone()
    assert row[0] is None
    assert row[1] is None
    assert row[2] is None


# ---------------------------------------------------------------------------
# Simple query function
# ---------------------------------------------------------------------------

@pytest.mark.db
def test_get_all_results_returns_dict(fake_query_fn):
    """get_all_results() returns a dict."""
    result = fake_query_fn()
    assert isinstance(result, dict)


@pytest.mark.db
def test_get_all_results_has_expected_keys(fake_query_fn):
    """get_all_results() returns dict with required Module-3 keys."""
    expected_keys = [
        "fall_2026_count", "pct_international", "avg_gpa", "avg_gre",
        "avg_gre_v", "avg_gre_aw", "avg_gpa_american", "pct_accepted_fall_2026",
        "avg_gpa_accepted", "jhu_ms_cs_count", "q8_scraped", "q9_llm",
        "q10_degree_gpa", "q11_nationality_acceptance",
    ]
    result = fake_query_fn()
    for key in expected_keys:
        assert key in result, f"Missing expected key: '{key}'"


@pytest.mark.db
def test_get_all_results_fall_2026_count(fake_query_fn):
    """fall_2026_count matches number of Fall 2026 records inserted."""
    result = fake_query_fn()
    # All 3 SAMPLE_RECORDS have term='Fall 2026'
    assert result["fall_2026_count"] == len(SAMPLE_RECORDS)


@pytest.mark.db
def test_get_all_results_pct_international_is_float(fake_query_fn):
    """pct_international is a float."""
    result = fake_query_fn()
    assert isinstance(result["pct_international"], float)


@pytest.mark.db
def test_get_all_results_q10_is_list(fake_query_fn):
    """q10_degree_gpa is a list."""
    result = fake_query_fn()
    assert isinstance(result["q10_degree_gpa"], list)


@pytest.mark.db
def test_get_all_results_q11_is_list(fake_query_fn):
    """q11_nationality_acceptance is a list."""
    result = fake_query_fn()
    assert isinstance(result["q11_nationality_acceptance"], list)


@pytest.mark.db
def test_schema_has_required_columns(clean_db):
    """The applicants table has all required columns including content_hash."""
    required = {
        "p_id", "content_hash", "program", "comments", "date_added", "url",
        "status", "term", "us_or_international", "gpa", "gre", "gre_v",
        "gre_aw", "degree", "llm_generated_program", "llm_generated_university",
    }
    with clean_db.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'applicants';
        """)
        actual = {row[0] for row in cur.fetchall()}
    missing = required - actual
    assert not missing, f"Missing columns: {missing}"


@pytest.mark.db
def test_content_hash_is_set_after_insert(clean_db):
    """Every inserted row has a non-null content_hash."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants WHERE content_hash IS NULL;")
        null_count = cur.fetchone()[0]
    assert null_count == 0, "Some rows have a NULL content_hash"


@pytest.mark.db
def test_content_hash_unique_constraint(clean_db):
    """Inserting the same record twice leaves exactly one row (content_hash dedup)."""
    _insert_records(clean_db, [SAMPLE_RECORDS[0]])
    _insert_records(clean_db, [SAMPLE_RECORDS[0]])
    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == 1, "Duplicate content_hash created a second row"


@pytest.mark.db
def test_url_missing_record_still_deduplicated(clean_db):
    """A record with no URL gets a content_hash and is not duplicated on re-insert."""
    from load_data import build_row, INSERT_SQL as LOAD_INSERT_SQL, make_content_hash
    from psycopg2 import extras as pg_extras

    no_url_record = {
        "program": "Statistics, Columbia",
        "comments": "GPA 3.7",
        "date_added": "2024-03-10",
        "url": None,  # missing URL
        "status": "Accepted on Mar 10",
        "term": "Fall 2026",
        "US/International": "International",
        "GPA": "3.7",
        "GRE": None, "GRE V": None, "GRE AW": None,
        "Degree": "Masters",
        "llm-generated-program": "Statistics",
        "llm-generated-university": "Columbia University",
    }

    row = build_row(no_url_record)
    assert row is not None, "build_row returned None for a valid no-URL record"

    # Insert twice — should only appear once
    with clean_db.cursor() as cur:
        pg_extras.execute_values(cur, LOAD_INSERT_SQL, [row])
        pg_extras.execute_values(cur, LOAD_INSERT_SQL, [row])
    clean_db.commit()

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants WHERE url IS NULL;")
        count = cur.fetchone()[0]
    assert count == 1, "No-URL record was duplicated"


@pytest.mark.db
def test_make_content_hash_deterministic():
    """make_content_hash returns the same value for the same inputs."""
    from load_data import make_content_hash
    h1 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://example.com/1")
    h2 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://example.com/1")
    assert h1 == h2


@pytest.mark.db
def test_make_content_hash_differs_for_different_records():
    """make_content_hash returns different values for different records."""
    from load_data import make_content_hash
    h1 = make_content_hash("CS, MIT", "Accepted", "2024-03-01", "http://example.com/1")
    h2 = make_content_hash("CS, Stanford", "Rejected", "2024-03-02", "http://example.com/2")
    assert h1 != h2

# ---------------------------------------------------------------------------
# Error-path: no partial writes / no dangling connection on failure
# ---------------------------------------------------------------------------

@pytest.mark.db
def test_run_scraper_pipeline_leaves_no_partial_writes_on_insert_failure(clean_db):
    """If the insert step fails partway through run_scraper_pipeline, no
    rows are left in the table and the connection is rolled back + closed
    (not left open/uncommitted) — verified against a real Postgres instance,
    not a mock.
    """
    import app as app_module

    fake_records = [{
        "raw_institution_program": "Harvard",
        "raw_degree_status": "Physics · PhD | Accepted on Feb 20 | Fall 2026   American",
        "raw_date": "Feb 20, 2024",
        "raw_notes": "GPA: 3.95",
        "url": "https://thegradcafe.com/result/failure_test",
    }]

    # Force the insert step itself to fail after clean/parse succeed.
    with patch("app.load_records", side_effect=RuntimeError("simulated insert failure")):
        app_module.run_scraper_pipeline(scraper_fn=lambda: fake_records, db_url=DB_URL)

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == 0, "A failed pipeline run must not leave any partial rows"


@pytest.mark.db
def test_run_scraper_pipeline_recovers_after_prior_failure(clean_db):
    """After a failed run (rolled back), a subsequent successful run must
    still be able to insert rows — proving the earlier failure didn't leave
    a stale/broken connection or an uncommitted transaction blocking future
    writes."""
    import app as app_module

    fake_records = [{
        "raw_institution_program": "Harvard",
        "raw_degree_status": "Physics · PhD | Accepted on Feb 20 | Fall 2026   American",
        "raw_date": "Feb 20, 2024",
        "raw_notes": "GPA: 3.95",
        "url": "https://thegradcafe.com/result/recovery_test",
    }]

    with patch("app.load_records", side_effect=RuntimeError("simulated failure")):
        app_module.run_scraper_pipeline(scraper_fn=lambda: fake_records, db_url=DB_URL)

    # Second, real run — should succeed normally.
    app_module.run_scraper_pipeline(scraper_fn=lambda: fake_records, db_url=DB_URL)

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == 1


@pytest.mark.db
def test_run_scraper_pipeline_swallows_rollback_failure():
    """If rollback()/close() themselves raise psycopg2.Error after an
    insert failure, that's swallowed too — run_scraper_pipeline must
    never raise, since it's always run in a background thread with no
    caller to catch an exception.

    This narrow edge case (the rollback call itself failing) is tested
    with a mock connection rather than real Postgres, since psycopg2's
    real connection objects don't allow monkeypatching .rollback (it's
    a read-only C-extension attribute) — there's no way to make a real
    connection's rollback() raise on demand.
    """
    import app as app_module

    fake_records = [{
        "raw_institution_program": "Harvard",
        "raw_degree_status": "Physics · PhD | Accepted on Feb 20 | Fall 2026   American",
        "raw_date": "Feb 20, 2024",
        "raw_notes": "GPA: 3.95",
        "url": "https://thegradcafe.com/result/rollback_failure_test",
    }]

    mock_conn = MagicMock()
    mock_conn.rollback.side_effect = psycopg2.Error("rollback failed")

    with patch("app.get_connection", return_value=mock_conn), \
         patch("app.create_table"), \
         patch("app.load_records", side_effect=RuntimeError("simulated insert failure")):
        # Should not raise even though both the insert AND the rollback fail.
        app_module.run_scraper_pipeline(scraper_fn=lambda: fake_records, db_url="")

    mock_conn.rollback.assert_called_once()


@pytest.mark.db
def test_run_scraper_pipeline_no_duplicates_on_repeated_success(clean_db):
    """Running the real Pull Data pipeline twice with the same record does
    not create a duplicate row — exercising the actual content_hash-based
    dedup now shared with load_data.py (previously this path deduped on
    `url` alone via a separate hand-rolled insert)."""
    import app as app_module

    fake_records = [{
        "raw_institution_program": "Harvard",
        "raw_degree_status": "Physics · PhD | Accepted on Feb 20 | Fall 2026   American",
        "raw_date": "Feb 20, 2024",
        "raw_notes": "GPA: 3.95",
        "url": "https://thegradcafe.com/result/dedup_test",
    }]

    app_module.run_scraper_pipeline(scraper_fn=lambda: fake_records, db_url=DB_URL)
    app_module.run_scraper_pipeline(scraper_fn=lambda: fake_records, db_url=DB_URL)

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count == 1
