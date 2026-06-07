"""
load_data.py
------------
Connects to a PostgreSQL database and loads cleaned Grad Café applicant data
from a CSV file (produced in Module 2) into an `applicants` table.

Usage:
    python load_data.py --csv <path_to_csv>

Environment variables (or edit DB_CONFIG below):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

import os
import csv
import argparse
import psycopg2
from psycopg2 import sql, extras

# ---------------------------------------------------------------------------
# Database connection config — override via environment variables or edit here
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "gradcafe",   # whatever you named your database
    "user":     "postgres",   # your PostgreSQL username
    "password": "yourpassword",  # your PostgreSQL password
}

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
ON CONFLICT DO NOTHING;
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
    return psycopg2.connect(**DB_CONFIG)


def create_table(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    print("✓ Table `applicants` ready.")


def load_csv(conn, csv_path: str):
    rows = []
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rows.append((
                    row.get("program"),
                    row.get("comments"),
                    parse_date(row.get("date_added")),
                    row.get("url"),
                    row.get("status"),
                    row.get("term"),
                    row.get("us_or_international"),
                    parse_float(row.get("gpa")),
                    parse_float(row.get("gre")),
                    parse_float(row.get("gre_v")),
                    parse_float(row.get("gre_aw")),
                    row.get("degree"),
                    row.get("llm_generated_program"),
                    row.get("llm_generated_university"),
                ))
            except Exception as e:
                skipped += 1
                print(f"  ⚠ Skipping row due to error: {e}")

    if not rows:
        print("No valid rows found in CSV. Exiting.")
        return

    with conn.cursor() as cur:
        extras.execute_values(cur, INSERT_SQL, rows, page_size=500)
    conn.commit()

    print(f"✓ Inserted {len(rows)} rows ({skipped} skipped) into `applicants`.")


def main():
    parser = argparse.ArgumentParser(description="Load Grad Café data into PostgreSQL.")
    parser.add_argument("--csv", required=True, help="Path to cleaned CSV file from Module 2.")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}")
        return

    try:
        conn = get_connection()
        print(f"✓ Connected to database `{DB_CONFIG['dbname']}` on {DB_CONFIG['host']}.")
    except psycopg2.OperationalError as e:
        print(f"✗ Could not connect to database: {e}")
        return

    try:
        create_table(conn)
        load_csv(conn, args.csv)
    finally:
        conn.close()
        print("✓ Connection closed.")


if __name__ == "__main__":
    main()
