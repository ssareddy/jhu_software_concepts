"""
query_data.py
-------------
Answers required analysis questions using SQL queries against the
``applicants`` PostgreSQL table populated by load_data.py.

Connection is resolved entirely from environment variables via db_config.py:

    DATABASE_URL=postgresql://user:pass@host/gradcafe python query_data.py

or with individual variables:

    DB_HOST=localhost DB_PORT=5432 DB_NAME=gradcafe DB_USER=postgres DB_PASSWORD=secret python query_data.py

No credentials are hard-coded here.
"""

import os
import psycopg2

from db_config import get_db_config, get_connection

# Re-export DB_CONFIG as a mutable dict so tests can patch it without
# touching the environment.  Always reflects the current environment at
# import time; tests that need a different DB should set DATABASE_URL
# before importing, or patch db_config.get_db_config directly.
DB_CONFIG = get_db_config()


def _conn():
    """Open a connection using the current DB_CONFIG (patchable by tests)."""
    return psycopg2.connect(**DB_CONFIG)


def run_queries():  # pragma: no cover
    conn = _conn()
    cur = conn.cursor()

    # Q1
    cur.execute("SELECT COUNT(*) FROM applicants WHERE term ILIKE '%Fall 2026%';")
    fall_2026_count = cur.fetchone()[0]
    print(f"Applicant count: {fall_2026_count}")

    # Q2
    cur.execute("""
        SELECT
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE us_or_international ILIKE '%international%'
                                          AND us_or_international NOT ILIKE '%american%'
                                          AND us_or_international NOT ILIKE '%other%')
                / NULLIF(COUNT(*), 0),
                2
            ) AS pct_international,
            COUNT(*) FILTER (WHERE us_or_international ILIKE '%international%'
                              AND us_or_international NOT ILIKE '%american%'
                              AND us_or_international NOT ILIKE '%other%') AS intl_count,
            COUNT(*) FILTER (WHERE us_or_international ILIKE '%american%') AS us_count,
            COUNT(*) FILTER (WHERE us_or_international ILIKE '%other%') AS other_count
        FROM applicants;
    """)
    row = cur.fetchone()
    pct_intl, intl_count, us_count, other_count = row
    print(f"International count: {intl_count}")
    print(f"US count: {us_count}")
    print(f"Other count: {other_count}")
    print(f"Percent International {pct_intl}")

    # Q3
    cur.execute("""
        SELECT
            ROUND(AVG(gpa)::numeric,   2) AS avg_gpa,
            ROUND(AVG(CASE WHEN gre BETWEEN 130 AND 170 THEN gre END)::numeric,   2) AS avg_gre,
            ROUND(AVG(CASE WHEN gre_v BETWEEN 130 AND 170 THEN gre_v END)::numeric, 2) AS avg_gre_v,
            ROUND(AVG(CASE WHEN gre_aw BETWEEN 0 AND 6 THEN gre_aw END)::numeric,2) AS avg_gre_aw
        FROM applicants
        WHERE gpa IS NOT NULL
           OR gre IS NOT NULL
           OR gre_v IS NOT NULL
           OR gre_aw IS NOT NULL;
    """)
    avg_gpa, avg_gre, avg_gre_v, avg_gre_aw = cur.fetchone()
    print(f"Average GPA: {avg_gpa}, Average GRE: {avg_gre}, "
          f"Average GRE V: {avg_gre_v}, Average GRE AW: {avg_gre_aw}")

    # Q4
    cur.execute("""
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term ILIKE '%Fall 2026%'
          AND us_or_international ILIKE '%american%'
          AND gpa IS NOT NULL;
    """)
    avg_gpa_american = cur.fetchone()[0]
    print(f"Average GPA American: {avg_gpa_american}")

    # Q5
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status ILIKE '%accept%') AS accept_count,
            COUNT(*) AS total,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status ILIKE '%accept%')
                / NULLIF(COUNT(*), 0),
                2
            ) AS pct_accepted
        FROM applicants
        WHERE term ILIKE '%Fall 2026%';
    """)
    accept_count, total_fall, pct_accepted = cur.fetchone()
    print(f"Acceptance count: {accept_count}")
    print(f"Acceptance percent: {pct_accepted}")

    # Q6
    cur.execute("""
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term ILIKE '%Fall 2026%'
          AND status ILIKE '%accept%'
          AND gpa IS NOT NULL;
    """)
    avg_gpa_accepted = cur.fetchone()[0]
    print(f"Average GPA Acceptance: {avg_gpa_accepted}")

    # Q7
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE (
            program ILIKE '%Johns Hopkins%'
            OR program ILIKE '%JHU%'
            OR llm_generated_university ILIKE '%Johns Hopkins%'
        )
          AND degree ILIKE '%master%'
          AND (
            program ILIKE '%computer science%'
            OR llm_generated_program ILIKE '%computer science%'
          );
    """)
    jhu_ms_cs_count = cur.fetchone()[0]
    print(f"JHU Masters Computer Science count: {jhu_ms_cs_count}")

    # Q8
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%2026%'
          AND status ILIKE '%accept%'
          AND degree ILIKE '%ph%'
          AND program ILIKE '%computer science%'
          AND (
            program ILIKE '%Georgetown%'
            OR program ILIKE '%Massachusetts Institute%'
            OR program ILIKE '%MIT%'
            OR program ILIKE '%Stanford%'
            OR program ILIKE '%Carnegie Mellon%'
            OR program ILIKE '%CMU%'
          );
    """)
    q8_scraped_count = cur.fetchone()[0]
    print(f"Q8 (Scraped fields) - PhD CS Acceptances at top schools in 2026: {q8_scraped_count}")

    # Q9
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%2026%'
          AND status ILIKE '%accept%'
          AND degree ILIKE '%ph%'
          AND llm_generated_program ILIKE '%computer science%'
          AND (
            llm_generated_university ILIKE '%Georgetown%'
            OR llm_generated_university ILIKE '%Massachusetts Institute%'
            OR llm_generated_university ILIKE '%MIT%'
            OR llm_generated_university ILIKE '%Stanford%'
            OR llm_generated_university ILIKE '%Carnegie Mellon%'
            OR llm_generated_university ILIKE '%CMU%'
          );
    """)
    q9_llm_count = cur.fetchone()[0]
    print(f"Q9 (LLM fields) - PhD CS Acceptances at top schools in 2026: {q9_llm_count}")

    # Q10
    cur.execute("""
        SELECT
            CASE
                WHEN degree ILIKE '%ph%' THEN 'PhD'
                WHEN degree ILIKE '%master%' OR degree ILIKE '%ms%' OR degree ILIKE '%m.s%' THEN 'Masters'
                ELSE 'Other'
            END AS degree_type,
            ROUND(AVG(gpa)::numeric, 2) AS avg_gpa,
            COUNT(*) AS total
        FROM applicants
        WHERE term ILIKE '%Fall 2026%'
          AND gpa IS NOT NULL
        GROUP BY degree_type
        ORDER BY avg_gpa DESC;
    """)
    print("\nCustom Q10: Average GPA by Degree Type (Fall 2026)")
    for row in cur.fetchall():
        print(f"  {row[0]}: avg GPA = {row[1]}, count = {row[2]}")

    # Q11
    cur.execute("""
        SELECT
            us_or_international,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status ILIKE '%accept%') AS accepted,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status ILIKE '%accept%')
                / NULLIF(COUNT(*), 0),
                2
            ) AS accept_rate
        FROM applicants
        WHERE term ILIKE '%Fall 2026%'
          AND degree ILIKE '%ph%'
          AND (
            program ILIKE '%computer science%'
            OR llm_generated_program ILIKE '%computer science%'
          )
          AND us_or_international IS NOT NULL
        GROUP BY us_or_international
        ORDER BY accept_rate DESC;
    """)
    print("\nCustom Q11: PhD CS Fall 2026 Acceptance Rate by Nationality")
    for row in cur.fetchall():
        print(f"  {row[0]}: total={row[1]}, accepted={row[2]}, rate={row[3]}%")

    cur.close()
    conn.close()


def get_all_results() -> dict:
    """
    Run all analysis queries and return a dict consumed by the Flask API.

    Returns
    -------
    dict
        Keys match the template variables used in index.html.
    """
    conn = _conn()
    cur = conn.cursor()
    results = {}

    cur.execute("SELECT COUNT(*) FROM applicants WHERE term ILIKE '%Fall 2026%';")
    results["fall_2026_count"] = cur.fetchone()[0]

    cur.execute("""
        SELECT
            ROUND(100.0 * COUNT(*) FILTER (WHERE us_or_international ILIKE '%international%'
                                            AND us_or_international NOT ILIKE '%american%'
                                            AND us_or_international NOT ILIKE '%other%')
                  / NULLIF(COUNT(*), 0), 2)
        FROM applicants;
    """)
    results["pct_international"] = float(cur.fetchone()[0] or 0)

    cur.execute("""
        SELECT
            ROUND(AVG(gpa)::numeric,   2),
            ROUND(AVG(CASE WHEN gre BETWEEN 130 AND 170 THEN gre END)::numeric,   2),
            ROUND(AVG(CASE WHEN gre_v BETWEEN 130 AND 170 THEN gre_v END)::numeric, 2),
            ROUND(AVG(CASE WHEN gre_aw BETWEEN 0 AND 6 THEN gre_aw END)::numeric,2)
        FROM applicants
        WHERE gpa IS NOT NULL OR gre IS NOT NULL OR gre_v IS NOT NULL OR gre_aw IS NOT NULL;
    """)
    r = cur.fetchone()
    results["avg_gpa"]    = float(r[0] or 0)
    results["avg_gre"]    = float(r[1] or 0)
    results["avg_gre_v"]  = float(r[2] or 0)
    results["avg_gre_aw"] = float(r[3] or 0)

    cur.execute("""
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term ILIKE '%Fall 2026%'
          AND us_or_international ILIKE '%american%'
          AND gpa IS NOT NULL;
    """)
    results["avg_gpa_american"] = float(cur.fetchone()[0] or 0)

    cur.execute("""
        SELECT
            ROUND(100.0 * COUNT(*) FILTER (WHERE status ILIKE '%accept%')
                  / NULLIF(COUNT(*), 0), 2)
        FROM applicants
        WHERE term ILIKE '%Fall 2026%';
    """)
    results["pct_accepted_fall_2026"] = float(cur.fetchone()[0] or 0)

    cur.execute("""
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term ILIKE '%Fall 2026%'
          AND status ILIKE '%accept%'
          AND gpa IS NOT NULL;
    """)
    results["avg_gpa_accepted"] = float(cur.fetchone()[0] or 0)

    cur.execute("""
        SELECT COUNT(*) FROM applicants
        WHERE (program ILIKE '%Johns Hopkins%' OR program ILIKE '%JHU%'
               OR llm_generated_university ILIKE '%Johns Hopkins%')
          AND degree ILIKE '%master%'
          AND (program ILIKE '%computer science%' OR llm_generated_program ILIKE '%computer science%');
    """)
    results["jhu_ms_cs_count"] = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM applicants
        WHERE term ILIKE '%2026%' AND status ILIKE '%accept%' AND degree ILIKE '%ph%'
          AND program ILIKE '%computer science%'
          AND (program ILIKE '%Georgetown%' OR program ILIKE '%Massachusetts Institute%'
               OR program ILIKE '%MIT%' OR program ILIKE '%Stanford%'
               OR program ILIKE '%Carnegie Mellon%' OR program ILIKE '%CMU%');
    """)
    results["q8_scraped"] = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM applicants
        WHERE term ILIKE '%2026%' AND status ILIKE '%accept%' AND degree ILIKE '%ph%'
          AND llm_generated_program ILIKE '%computer science%'
          AND (llm_generated_university ILIKE '%Georgetown%'
               OR llm_generated_university ILIKE '%Massachusetts Institute%'
               OR llm_generated_university ILIKE '%MIT%'
               OR llm_generated_university ILIKE '%Stanford%'
               OR llm_generated_university ILIKE '%Carnegie Mellon%'
               OR llm_generated_university ILIKE '%CMU%');
    """)
    results["q9_llm"] = cur.fetchone()[0]

    cur.execute("""
        SELECT
            CASE WHEN degree ILIKE '%ph%' THEN 'PhD'
                 WHEN degree ILIKE '%master%' OR degree ILIKE '%ms%' OR degree ILIKE '%m.s%' THEN 'Masters'
                 ELSE 'Other' END AS degree_type,
            ROUND(AVG(gpa)::numeric, 2) AS avg_gpa,
            COUNT(*) AS total
        FROM applicants
        WHERE term ILIKE '%Fall 2026%' AND gpa IS NOT NULL
        GROUP BY degree_type ORDER BY avg_gpa DESC;
    """)
    results["q10_degree_gpa"] = [
        {"degree_type": r[0], "avg_gpa": float(r[1] or 0), "count": r[2]}
        for r in cur.fetchall()
    ]

    cur.execute("""
        SELECT us_or_international,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status ILIKE '%accept%') AS accepted,
            ROUND(100.0 * COUNT(*) FILTER (WHERE status ILIKE '%accept%')
                  / NULLIF(COUNT(*), 0), 2) AS accept_rate
        FROM applicants
        WHERE term ILIKE '%Fall 2026%' AND degree ILIKE '%ph%'
          AND (program ILIKE '%computer science%' OR llm_generated_program ILIKE '%computer science%')
          AND us_or_international IS NOT NULL
        GROUP BY us_or_international ORDER BY accept_rate DESC;
    """)
    results["q11_nationality_acceptance"] = [
        {"nationality": r[0], "total": r[1], "accepted": r[2], "rate": float(r[3] or 0)}
        for r in cur.fetchall()
    ]

    cur.close()
    conn.close()
    return results


if __name__ == "__main__":  # pragma: no cover
    run_queries()