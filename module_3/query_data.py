"""
query_data.py
-------------
Answers required analysis questions using SQL queries against the
`applicants` PostgreSQL table populated by load_data.py.

Usage:
    python query_data.py

Environment variables (or edit DB_CONFIG):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

import os
import psycopg2

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "gradcafe",   # whatever you named your database
    "user":     "postgres",   # your PostgreSQL username
    "password": "yourpassword",  # your PostgreSQL password
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def run_queries():
    conn = get_connection()
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # Q1: How many entries applied for Fall 2026?
    # Filter rows where `term` contains 'Fall 2026'.
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%Fall 2026%';
    """)
    fall_2026_count = cur.fetchone()[0]
    print(f"Applicant count: {fall_2026_count}")

    # ------------------------------------------------------------------
    # Q2: Percentage of international students (not American or Other)
    # We count rows where us_or_international is 'International', then
    # divide by total non-null entries and multiply by 100.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Q3: Average GPA, GRE, GRE V, GRE AW for applicants who provided them.
    # AVG() automatically ignores NULLs, so only rows with values count.
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT
            ROUND(AVG(gpa)::numeric,   2) AS avg_gpa,
            ROUND(AVG(gre)::numeric,   2) AS avg_gre,
            ROUND(AVG(gre_v)::numeric, 2) AS avg_gre_v,
            ROUND(AVG(gre_aw)::numeric,2) AS avg_gre_aw
        FROM applicants
        WHERE gpa IS NOT NULL
           OR gre IS NOT NULL
           OR gre_v IS NOT NULL
           OR gre_aw IS NOT NULL;
    """)
    avg_gpa, avg_gre, avg_gre_v, avg_gre_aw = cur.fetchone()
    print(f"Average GPA: {avg_gpa}, Average GRE: {avg_gre}, "
          f"Average GRE V: {avg_gre_v}, Average GRE AW: {avg_gre_aw}")

    # ------------------------------------------------------------------
    # Q4: Average GPA of American students in Fall 2026.
    # Filter to Fall 2026 term and American nationality.
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term ILIKE '%Fall 2026%'
          AND us_or_international ILIKE '%american%'
          AND gpa IS NOT NULL;
    """)
    avg_gpa_american = cur.fetchone()[0]
    print(f"Average GPA American: {avg_gpa_american}")

    # ------------------------------------------------------------------
    # Q5: Percent of Fall 2026 entries that are Acceptances.
    # Filter to Fall 2026 term; count where status = 'Accepted'.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Q6: Average GPA of Fall 2026 Accepted applicants.
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term ILIKE '%Fall 2026%'
          AND status ILIKE '%accept%'
          AND gpa IS NOT NULL;
    """)
    avg_gpa_accepted = cur.fetchone()[0]
    print(f"Average GPA Acceptance: {avg_gpa_accepted}")

    # ------------------------------------------------------------------
    # Q7: Entries from applicants who applied to JHU for a Masters in CS.
    # Use llm_generated_university for JHU and degree for Masters, program for CS.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Q8: Fall 2026 acceptances to Georgetown, MIT, Stanford, or CMU for PhD CS
    # using the downloaded (scraped) program/university fields.
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%2026%'
          AND status ILIKE '%accept%'
          AND degree ILIKE '%ph%'
          AND (
            program ILIKE '%computer science%'
          )
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

    # ------------------------------------------------------------------
    # Q9: Same as Q8, but using LLM-generated fields instead.
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%2026%'
          AND status ILIKE '%accept%'
          AND degree ILIKE '%ph%'
          AND (
            llm_generated_program ILIKE '%computer science%'
          )
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
    print(f"Q9 (LLM fields)    - PhD CS Acceptances at top schools in 2026: {q9_llm_count}")
    if q8_scraped_count != q9_llm_count:
        print(f"  → Numbers differ: scraped={q8_scraped_count}, LLM={q9_llm_count}. "
              "LLM fields tend to normalize university names, capturing more matches.")
    else:
        print("  → Numbers are the same with both field types.")

    # ------------------------------------------------------------------
    # CUSTOM Q10: Which degree type (PhD vs Masters) has the higher
    # average GPA among Fall 2026 applicants?
    # Motivation: Understand if PhD applicants are stronger academically.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # CUSTOM Q11: What is the acceptance rate by nationality (American vs
    # International) for Fall 2026 PhD Computer Science applicants?
    # Motivation: Examine whether nationality correlates with PhD CS admissions.
    # ------------------------------------------------------------------
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


def get_all_results():
    """
    Returns a dict of all query results for use by the Flask app.
    """
    conn = get_connection()
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
            ROUND(AVG(gre)::numeric,   2),
            ROUND(AVG(gre_v)::numeric, 2),
            ROUND(AVG(gre_aw)::numeric,2)
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

    # Custom Q10
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

    # Custom Q11
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


if __name__ == "__main__":
    run_queries()
