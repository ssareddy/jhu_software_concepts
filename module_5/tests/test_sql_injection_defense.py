"""
tests/test_sql_injection_defense.py
------------------------------------
Demonstrates that /api/search — the one Flask route that actually accepts
user-supplied input feeding into a SQL query — is safe against injection
and abuse.

Prior to this file, get_filtered_results() (the safely-parameterized
query using psycopg2.sql.SQL/Identifier) existed but wasn't reachable
from any route, so there was no endpoint-level proof that malicious
input is handled safely. These tests exercise the real route, against a
real Postgres table, with real attack-style payloads.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# A representative set of SQL injection / abuse payloads for the `term`
# query parameter. None of these should ever be treated as SQL — they
# should all be searched for literally as a substring, matching nothing
# in the seeded data (which contains no such strings).
INJECTION_PAYLOADS = [
    "'; DROP TABLE applicants; --",
    "' OR '1'='1",
    "' OR 1=1 --",
    "'; SELECT * FROM applicants; --",
    "Fall' UNION SELECT program, comments, date_added, url, status, term, "
    "us_or_international, gpa, gre, gre_v, gre_aw, degree, "
    "llm_generated_program, llm_generated_university FROM applicants --",
    "\"; DROP TABLE applicants; --",
    "%' OR '%'='",
]


@pytest.mark.web
@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_search_injection_payload_does_not_crash(client_with_db, payload):
    """A SQL-injection-style `term` value returns 200, not a crash or 500."""
    resp = client_with_db.get("/api/search", query_string={"term": payload})
    assert resp.status_code == 200


@pytest.mark.web
@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_search_injection_payload_returns_no_unintended_data(client_with_db, payload):
    """A SQL-injection-style `term` is searched for literally — it matches
    nothing in the seeded data, and never returns the whole table (which
    a successful injection like `' OR '1'='1` or a UNION-based payload
    would achieve against a naive string-built query)."""
    resp = client_with_db.get("/api/search", query_string={"term": payload})
    data = resp.get_json()
    assert data["status"] == "ok"
    # None of the seeded records legitimately match these payloads, so a
    # safe implementation returns zero rows. A vulnerable implementation
    # (e.g. f"...ILIKE '%{term}%'") would instead return every row for
    # payloads like "' OR '1'='1" / "%' OR '%'='".
    assert data["count"] == 0
    assert data["data"] == []


@pytest.mark.web
def test_search_table_still_exists_after_drop_attempt(client_with_db, seeded_db):
    """A DROP TABLE payload in `term` does not actually drop the table —
    the table and its seeded rows are still present and queryable
    immediately after the request."""
    resp = client_with_db.get(
        "/api/search",
        query_string={"term": "'; DROP TABLE applicants; --"},
    )
    assert resp.status_code == 200

    with seeded_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        count = cur.fetchone()[0]
    assert count > 0, "applicants table was dropped or emptied by the injection attempt"


@pytest.mark.web
def test_search_legitimate_term_returns_matching_rows(client_with_db, seeded_db):
    """Sanity check: a normal, legitimate term still returns real matches
    (proves the injection tests above aren't just testing a broken route
    that returns nothing for everything)."""
    resp = client_with_db.get("/api/search", query_string={"term": "Fall 2026"})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["status"] == "ok"
    assert data["count"] > 0


@pytest.mark.web
def test_search_default_term_returns_200(client_with_db):
    """Omitting `term` entirely (empty string default) doesn't crash."""
    resp = client_with_db.get("/api/search")
    assert resp.status_code == 200


@pytest.mark.web
@pytest.mark.parametrize("bad_limit", [
    "99999999",       # wildly oversized — must be clamped, not honored
    "-1",              # negative
    "0",               # zero
    "not_a_number",    # non-numeric garbage
    "'; DROP TABLE applicants; --",  # injection attempt via limit itself
    "1 OR 1=1",
])
def test_search_limit_abuse_does_not_crash_or_bypass_clamp(client_with_db, seeded_db, bad_limit):
    """Malicious or malformed `limit` values never crash the route and
    never bypass the server-side clamp (1..MAX_LIMIT) to dump more rows
    than actually exist / than the clamp allows."""
    resp = client_with_db.get(
        "/api/search",
        query_string={"term": "Fall 2026", "limit": bad_limit},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"

    with seeded_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        total_rows = cur.fetchone()[0]

    # However the bad limit gets interpreted (falls back to a default,
    # gets clamped to 1, etc.), the response must never exceed either the
    # real row count or the module's MAX_LIMIT — both bound how much a
    # single malicious request could exfiltrate.
    from query_data import MAX_LIMIT
    assert data["count"] <= min(total_rows, MAX_LIMIT)


@pytest.mark.web
def test_search_uses_injected_filtered_fn_when_provided():
    """/api/search respects dependency injection via create_app(filtered_fn=...),
    consistent with how scraper_fn/loader_fn/query_fn are injected elsewhere —
    so this route is testable without hitting a real DB when desired."""
    import app as app_module

    def fake_filtered(term, limit):
        return [("fake-program", term, "Fall 2026", 3.9)][:limit]

    flask_app = app_module.create_app(filtered_fn=fake_filtered)
    client = flask_app.test_client()

    resp = client.get("/api/search", query_string={"term": "anything", "limit": "5"})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["data"] == [["fake-program", "anything", "Fall 2026", 3.9]]


@pytest.mark.web
def test_search_db_error_returns_500_not_crash():
    """If the underlying query function raises a DB error, /api/search
    returns a clean 500 with an error message — not a stack trace, crash,
    or partial/malformed response."""
    import app as app_module
    import psycopg2

    def failing_filtered(term, limit):
        raise psycopg2.OperationalError("simulated connection failure")

    flask_app = app_module.create_app(filtered_fn=failing_filtered)
    client = flask_app.test_client()

    resp = client.get("/api/search", query_string={"term": "Fall 2026"})
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["status"] == "error"
