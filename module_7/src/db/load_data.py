"""
load_data.py
------------
Connects to PostgreSQL and loads cleaned Grad Café applicant data.

Connection is configured entirely via environment variables — no
hard-coded credentials, no interactive prompts. See db_config.py.

    DATABASE_URL=postgresql://user:pass@host:5432/gradcafe python load_data.py --json data.json

Schema notes
------------
* ``url``          — UNIQUE constraint; primary deduplication key when present.
* ``content_hash`` — SHA-256 of (program, status, date_added, url) stored as
                     a secondary UNIQUE key. Catches duplicates whose URLs are
                     missing or malformed so they are never silently inserted.
* Records with a null/blank URL *and* a null content_hash are skipped with a
  warning rather than inserted, to avoid phantom duplicates.
"""

import os
import json
import hashlib
import argparse
import psycopg2
from psycopg2 import extras

from db_config import get_db_config, get_connection

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applicants (
    p_id                  SERIAL PRIMARY KEY,
    content_hash          TEXT UNIQUE,          -- SHA-256 dedup key (always set)
    program               TEXT,
    comments              TEXT,
    date_added            DATE,
    url                   TEXT UNIQUE,          -- source URL (null when missing)
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
)
VALUES %s
ON CONFLICT (content_hash) DO NOTHING;
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_float(val):
    """Return float or None for empty/invalid values."""
    try:
        return float(val) if val not in (None, "", "N/A", "n/a") else None
    except (ValueError, TypeError):
        return None


def parse_date(val):
    """Return stripped date string or None."""
    return val.strip() if val and val.strip() else None


def make_content_hash(program, status, date_added, url) -> str:
    """
    Compute a SHA-256 fingerprint of the four most-stable fields.

    Using multiple fields (not just url) means records without a URL
    still get a stable, collision-resistant dedup key based on their
    content, rather than being silently treated as unique every time.

    Parameters
    ----------
    program, status, date_added, url : str | None
        Raw field values; None is normalised to the empty string.

    Returns
    -------
    str
        64-character hex digest.
    """
    parts = "|".join([
        str(program or ""),
        str(status or ""),
        str(date_added or ""),
        str(url or ""),
    ])
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def build_row(row: dict) -> tuple | None:
    """
    Convert a cleaned record dict to an INSERT tuple.

    Returns None and logs a warning for records that have no URL *and*
    whose content hash would be based entirely on empty fields (i.e.
    completely empty records that carry no useful information).
    """
    program    = row.get("program")
    status     = row.get("status")
    date_added = parse_date(row.get("date_added"))
    url        = row.get("url") or None   # normalise "" → None

    content_hash = make_content_hash(program, status, date_added, url)

    # Guard: skip records with no URL and no meaningful content
    if not url and not program and not status:
        print("  ⚠ Skipping record with no URL, program, or status — nothing to identify it.")
        return None

    if not url:
        print(f"  ⚠ Record has no URL; using content_hash for dedup: {program!r} / {status!r}")

    return (
        content_hash,
        program,
        row.get("comments"),
        date_added,
        url,
        status,
        row.get("term"),
        row.get("US/International"),
        parse_float(row.get("GPA")),
        parse_float(row.get("GRE")),
        parse_float(row.get("GRE V")),
        parse_float(row.get("GRE AW")),
        row.get("Degree"),
        row.get("llm-generated-program"),
        row.get("llm-generated-university"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_table(conn):
    """Create the applicants table if it does not already exist."""
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    print("✓ Table `applicants` ready.")


def load_records(conn, records: list[dict]) -> tuple[int, int]:
    """
    Insert a list of cleaned record dicts into the applicants table.

    Parameters
    ----------
    conn    : psycopg2 connection
    records : list of cleaned record dicts (output of clean.clean_data)

    Returns
    -------
    (inserted_count, skipped_count)
    """
    rows = []
    skipped = 0

    for rec in records:
        try:
            row = build_row(rec)
            if row is not None:
                rows.append(row)
            else:
                skipped += 1
        except (ValueError, KeyError, TypeError) as exc:
            skipped += 1
            print(f"  Skipping row due to error: {exc}")

    if not rows:
        print("No valid rows to insert.")
        return 0, skipped

    with conn.cursor() as cur:
        extras.execute_values(cur, INSERT_SQL, rows, page_size=500)
    conn.commit()

    inserted = len(rows)
    print(f"✓ Processed {inserted} rows ({skipped} skipped) into `applicants`.")
    return inserted, skipped


def load_json(conn, json_path: str) -> tuple[int, int]:
    """
    Load records from a JSON file and insert them into the DB.

    Parameters
    ----------
    conn      : psycopg2 connection
    json_path : path to a cleaned applicant JSON file

    Returns
    -------
    (inserted_count, skipped_count)
    """
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return load_records(conn, data)


def main():
    """Entry point: parse CLI args, connect to DB, create table, and load JSON data."""
    default_json = os.path.join(os.path.dirname(__file__),
                                "..", "data", "llm_extend_applicant_data.json")
    parser = argparse.ArgumentParser(description="Load Grad Café data into PostgreSQL.")
    parser.add_argument(
        "--json",
        default=default_json,
        help="Path to cleaned JSON file (default: llm_extend_applicant_data.json).",
    )
    args = parser.parse_args()

    if not os.path.exists(args.json):
        print(f"Error: JSON file not found: {args.json}")
        return

    cfg = get_db_config()
    print(f"Connecting to {cfg['dbname']}@{cfg['host']}:{cfg['port']} as {cfg['user']} …")

    try:
        conn = get_connection()
        print("Connected.")
    except psycopg2.OperationalError as exc:
        print(f"✗ Could not connect: {exc}")
        return

    try:
        create_table(conn)
        load_json(conn, args.json)
    finally:
        conn.close()
        print("✓ Connection closed.")


if __name__ == "__main__":  # pragma: no cover
    main()
