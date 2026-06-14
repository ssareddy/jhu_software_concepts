"""
load_data.py
------------
Connects to a PostgreSQL database and loads cleaned Grad Café applicant data
from a JSON file into an `applicants` table.

Usage:
    python load_data.py --json <path_to_json>

Edit DB_CONFIG below to match your PostgreSQL setup before running.
If DB_PASSWORD is left blank, you will be prompted to enter it at runtime.
"""

import os
import json
import argparse
import getpass
import psycopg2
from psycopg2 import extras

# ---------------------------------------------------------------------------
# Database connection config — edit these values to match your setup
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "gradcafe",
    "user":     "postgres",
    "password": "",          # Leave blank to be prompted at runtime
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applicants (
    p_id                  SERIAL PRIMARY KEY,
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
    program, comments, date_added, url, status, term,
    us_or_international, gpa, gre, gre_v, gre_aw, degree,
    llm_generated_program, llm_generated_university
)
VALUES %s
ON CONFLICT (url) DO NOTHING;
"""


def parse_float(val):
    """Return float or None for empty/invalid values."""
    try:
        return float(val) if val not in (None, "", "N/A", "n/a") else None
    except (ValueError, TypeError):
        return None


def parse_date(val):
    """Return date string or None."""
    return val.strip() if val and val.strip() else None


def get_connection():
    config = DB_CONFIG.copy()
    if not config["password"]:
        config["password"] = getpass.getpass(
            f"Enter PostgreSQL password for user '{config['user']}': "
        )
    return psycopg2.connect(**config)


def create_table(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    print("✓ Table `applicants` ready.")


def load_json(conn, json_path: str):
    rows = []
    skipped = 0

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    for row in data:
        try:
            rows.append((
                row.get("program"),
                row.get("comments"),
                parse_date(row.get("date_added")),
                row.get("url"),
                row.get("status"),
                row.get("term"),
                row.get("US/International"),
                parse_float(row.get("GPA")),
                parse_float(row.get("GRE")),
                parse_float(row.get("GRE V")),
                parse_float(row.get("GRE AW")),
                row.get("Degree"),
                row.get("llm-generated-program"),
                row.get("llm-generated-university"),
            ))
        except Exception as e:
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
        print(f"✓ Connected to database `{DB_CONFIG['dbname']}` on {DB_CONFIG['host']}.")
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