"""
load_data.py
------------
Connects to a PostgreSQL database and loads cleaned Grad Café applicant data
from a JSON file into an `applicants` table.

Usage:
    python load_data.py --json <path_to_json>

Connection settings come from db_config.py (see that file for the
DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD environment
variables it reads).

Duplicate protection: each row's `row_hash` is a hash of its stable
content fields (program, comments, date_added, status, term, GPA/GRE
scores, degree). This is the conflict target on insert, so reloading
the same data is a no-op even when `url` is missing or malformed --
unlike relying on `url` uniqueness alone.
"""

import json
import argparse
import hashlib
import os
import psycopg2
from psycopg2 import extras

from db_config import get_connection

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applicants (
    p_id                  SERIAL PRIMARY KEY,
    program               TEXT,
    comments              TEXT,
    date_added            DATE,
    url                   TEXT,
    status                TEXT,
    term                  TEXT,
    us_or_international   TEXT,
    gpa                   FLOAT,
    gre                   FLOAT,
    gre_v                 FLOAT,
    gre_aw                FLOAT,
    degree                TEXT,
    llm_generated_program     TEXT,
    llm_generated_university  TEXT,
    row_hash               TEXT UNIQUE NOT NULL
);
"""

INSERT_SQL = """
INSERT INTO applicants (
    program, comments, date_added, url, status, term,
    us_or_international, gpa, gre, gre_v, gre_aw, degree,
    llm_generated_program, llm_generated_university, row_hash
)
VALUES %s
ON CONFLICT (row_hash) DO NOTHING;
"""

# Fields that make up a row's content hash, i.e. everything that identifies
# a *unique submission* rather than a storage detail like `url` (which can
# be missing/malformed) or the LLM-derived fields (which can change between
# re-runs of the LLM extension step without the underlying entry changing).
_HASH_FIELDS = (
    "program", "comments", "date_added", "status", "term",
    "gpa", "gre", "gre_v", "gre_aw", "degree",
)


def compute_row_hash(fields: dict) -> str:
    """Hash a row's stable content fields for duplicate detection.

    `fields` must contain all keys in _HASH_FIELDS. Used as the insert
    conflict target instead of `url`, since `url` can be missing or
    malformed on scraped entries. Keys are hashed in a fixed, sorted
    order so the result doesn't depend on dict insertion order.
    """
    key = "|".join(str(fields[name]) for name in _HASH_FIELDS)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_float(val):
    """Return float or None for empty/invalid values."""
    try:
        return float(val) if val not in (None, "", "N/A", "n/a") else None
    except (ValueError, TypeError):
        return None


def parse_date(val):
    """Return date string or None."""
    return val.strip() if val and val.strip() else None


def create_table(conn):
    """Create the `applicants` table if it doesn't already exist."""
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    print("✓ Table `applicants` ready.")


def _row_from_json(row: dict) -> tuple:
    """Build one applicants-table row tuple (including row_hash) from a
    single JSON record."""
    fields = {
        "program": row.get("program"),
        "comments": row.get("comments"),
        "date_added": parse_date(row.get("date_added")),
        "status": row.get("status"),
        "term": row.get("term"),
        "gpa": parse_float(row.get("GPA")),
        "gre": parse_float(row.get("GRE")),
        "gre_v": parse_float(row.get("GRE V")),
        "gre_aw": parse_float(row.get("GRE AW")),
        "degree": row.get("Degree"),
    }
    row_hash = compute_row_hash(fields)

    return (
        fields["program"],
        fields["comments"],
        fields["date_added"],
        row.get("url"),
        fields["status"],
        fields["term"],
        row.get("US/International"),
        fields["gpa"],
        fields["gre"],
        fields["gre_v"],
        fields["gre_aw"],
        fields["degree"],
        row.get("llm-generated-program"),
        row.get("llm-generated-university"),
        row_hash,
    )


def load_json(conn, json_path: str):
    """Read applicant records from `json_path` and insert them into the
    `applicants` table, skipping rows already present by row_hash."""
    rows = []
    skipped = 0

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    for row in data:
        try:
            rows.append(_row_from_json(row))
        except (KeyError, TypeError, ValueError) as e:
            skipped += 1
            print(f"  ⚠ Skipping row due to error: {e}")

    if not rows:
        print("No valid rows found in JSON. Exiting.")
        return

    with conn.cursor() as cur:
        extras.execute_values(cur, INSERT_SQL, rows, page_size=500)
    conn.commit()

    print(f"✓ Inserted {len(rows)} rows ({skipped} skipped) into `applicants`.")


def main():
    """CLI entry point: load a cleaned JSON file into PostgreSQL."""
    default_json = os.path.join(os.path.dirname(__file__), "llm_extend_applicant_data.json")
    parser = argparse.ArgumentParser(description="Load Grad Café data into PostgreSQL.")
    parser.add_argument(
        "--json",
        default=default_json,
        help="Path to cleaned JSON file (default: llm_extend_applicant_data.json in module_3/)."
    )
    args = parser.parse_args()

    if not os.path.exists(args.json):
        print(f"Error: JSON file not found: {args.json}")
        return

    try:
        conn = get_connection()
        print("✓ Connected to database.")
    except psycopg2.OperationalError as e:
        print(f"✗ Could not connect to database: {e}")
        return

    try:
        create_table(conn)
        load_json(conn, args.json)
    finally:
        conn.close()
        print("✓ Connection closed.")


if __name__ == "__main__":
    main()
