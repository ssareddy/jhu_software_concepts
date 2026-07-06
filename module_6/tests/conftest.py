"""
conftest.py — shared fixtures for the entire test suite.
"""
import os
import sys
import hashlib
import pytest
import psycopg2
from psycopg2 import extras

# Make src/web and src/web/app importable
SRC_WEB = os.path.join(os.path.dirname(__file__), "..", "src", "web")
SRC_WEB_APP = os.path.join(os.path.dirname(__file__), "..", "src", "web", "app")
SRC_DB = os.path.join(os.path.dirname(__file__), "..", "src", "db")
sys.path.insert(0, os.path.abspath(SRC_WEB_APP))
sys.path.insert(0, os.path.abspath(SRC_WEB))
sys.path.insert(0, os.path.abspath(SRC_DB))

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/gradcafe_test"
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applicants (
    p_id                  SERIAL PRIMARY KEY,
    content_hash          TEXT UNIQUE,
    program               TEXT,
    comments              TEXT,
    date_added            DATE,
    url                   TEXT UNIQUE,
    status                TEXT,
    term                  TEXT,
    us_or_international   TEXT,
    gpa                   FLOAT,
    gre                   FLOAT,
    gre_v                 FLOAT,
    gre_aw                FLOAT,
    degree                TEXT,
    llm_generated_program     TEXT,
    llm_generated_university  TEXT
);
"""

INSERT_SQL = """
INSERT INTO applicants (
    content_hash,
    program, comments, date_added, url, status, term,
    us_or_international, gpa, gre, gre_v, gre_aw, degree,
    llm_generated_program, llm_generated_university
) VALUES %s
ON CONFLICT (content_hash) DO NOTHING;
"""

SAMPLE_RECORDS = [
    {
        "program": "Computer Science, MIT",
        "comments": "GPA: 3.9, GRE V: 165, GRE Q: 170",
        "date_added": "2024-03-01",
        "url": "https://thegradcafe.com/result/1",
        "status": "Accepted on Mar 01",
        "term": "Fall 2026",
        "US/International": "American",
        "GPA": "3.9",
        "GRE": "335",
        "GRE V": "165",
        "GRE AW": "4.5",
        "Degree": "PhD",
        "llm-generated-program": "Computer Science",
        "llm-generated-university": "Massachusetts Institute of Technology",
    },
    {
        "program": "Computer Science, Stanford",
        "comments": "GPA: 3.8",
        "date_added": "2024-03-02",
        "url": "https://thegradcafe.com/result/2",
        "status": "Rejected on Feb 15",
        "term": "Fall 2026",
        "US/International": "International",
        "GPA": "3.8",
        "GRE": None,
        "GRE V": None,
        "GRE AW": None,
        "Degree": "Masters",
        "llm-generated-program": "Computer Science",
        "llm-generated-university": "Stanford University",
    },
    {
        "program": "Physics, Harvard",
        "comments": "",
        "date_added": "2024-02-20",
        "url": "https://thegradcafe.com/result/3",
        "status": "Accepted on Feb 20",
        "term": "Fall 2026",
        "US/International": "American",
        "GPA": "3.95",
        "GRE": None,
        "GRE V": None,
        "GRE AW": None,
        "Degree": "PhD",
        "llm-generated-program": "Physics",
        "llm-generated-university": "Harvard University",
    },
]


def _get_db_conn():
    """Open a connection to the test database."""
    return psycopg2.connect(DB_URL)


def _reset_table(conn):
    """Drop and recreate applicants table for a clean slate."""
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS applicants;")
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()


def _insert_records(conn, records):
    """Insert records into the applicants table using content_hash dedup."""
    def pf(val):
        try:
            return float(val) if val not in (None, "", "N/A") else None
        except (ValueError, TypeError):
            return None

    def make_hash(program, status, date_added, url):
        parts = "|".join([str(x or "") for x in [program, status, date_added, url]])
        return hashlib.sha256(parts.encode()).hexdigest()

    rows = []
    for r in records:
        program    = r.get("program")
        status     = r.get("status")
        date_added = r.get("date_added")
        url        = r.get("url") or None
        rows.append((
            make_hash(program, status, date_added, url),
            program, r.get("comments"), date_added,
            url, status, r.get("term"),
            r.get("US/International"), pf(r.get("GPA")),
            pf(r.get("GRE")), pf(r.get("GRE V")),
            pf(r.get("GRE AW")), r.get("Degree"),
            r.get("llm-generated-program"), r.get("llm-generated-university"),
        ))
    with conn.cursor() as cur:
        extras.execute_values(cur, INSERT_SQL, rows)
    conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_conn():
    """Single DB connection for the session; ensures table exists."""
    conn = _get_db_conn()
    _reset_table(conn)
    yield conn
    conn.close()


@pytest.fixture()
def clean_db(db_conn):
    """Reset table before each test that touches the DB."""
    _reset_table(db_conn)
    yield db_conn
    _reset_table(db_conn)


@pytest.fixture()
def seeded_db(clean_db):
    """DB with SAMPLE_RECORDS loaded."""
    _insert_records(clean_db, SAMPLE_RECORDS)
    yield clean_db


@pytest.fixture()
def fake_query_fn(seeded_db):
    """A query_fn that runs real SQL against the test DB."""
    import urllib.parse as up
    import query_data
    orig = query_data.DB_CONFIG.copy()
    r = up.urlparse(DB_URL)
    query_data.DB_CONFIG.update({
        "host": r.hostname,
        "port": r.port or 5432,
        "dbname": r.path.lstrip("/"),
        "user": r.username,
        "password": r.password or "",
    })
    yield query_data.get_all_results
    query_data.DB_CONFIG.update(orig)


@pytest.fixture()
def mock_query_fn():
    """Returns a callable that yields a known analysis dict."""
    def _q():
        return {
            "fall_2026_count": 3,
            "pct_international": 33.33,
            "avg_gpa": 3.88,
            "avg_gre": 335.0,
            "avg_gre_v": 165.0,
            "avg_gre_aw": 4.5,
            "avg_gpa_american": 3.93,
            "pct_accepted_fall_2026": 66.67,
            "avg_gpa_accepted": 3.93,
            "jhu_ms_cs_count": 0,
            "q8_scraped": 1,
            "q9_llm": 1,
            "q10_degree_gpa": [
                {"degree_type": "PhD", "avg_gpa": 3.93, "count": 2},
                {"degree_type": "Masters", "avg_gpa": 3.80, "count": 1},
            ],
            "q11_nationality_acceptance": [
                {"nationality": "American", "total": 2, "accepted": 2, "rate": 100.0},
                {"nationality": "International", "total": 1, "accepted": 0, "rate": 0.0},
            ],
        }
    return _q


@pytest.fixture()
def app(mock_query_fn):
    """Flask test app with mocked query and mocked publisher."""
    from unittest.mock import patch
    from app import app as app_module
    flask_app = app_module.create_app(query_fn=mock_query_fn)
    flask_app.config["TESTING"] = True
    flask_app.config["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"
    with patch("app.app.publish_task"):
        yield flask_app


@pytest.fixture()
def client(app):
    """Test client for the Flask app."""
    return app.test_client()


@pytest.fixture()
def app_with_db(fake_query_fn):
    """Flask test app wired to the real test DB."""
    from unittest.mock import patch
    from app import app as app_module
    flask_app = app_module.create_app(query_fn=fake_query_fn)
    flask_app.config["TESTING"] = True
    flask_app.config["DATABASE_URL"] = DB_URL
    flask_app.config["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"
    with patch("app.app.publish_task"):
        yield flask_app


@pytest.fixture()
def client_with_db(app_with_db):
    """Test client wired to the real test DB."""
    return app_with_db.test_client()