"""One-time conversion script (NOT part of the graded submission).

Converts the raw Grad Cafe dataset (llm_extend_applicant_data.json, used in
prior modules) into the JSON-Lines applicant dataset format Module 12
expects: one JSON object per line, with fields gpa, gre, gre_v, gre_aw,
masters_or_phd, citizenship, and applicant_status.

Numeric fields are deliberately written as strings (matching the
assignment's description of "string-valued numeric columns"), and no
filtering or cleaning is applied here -- all filtering, type conversion,
and missing-value handling happens inside neural_network.py itself, as
required by the assignment.
"""

import json
import re

import pandas as pd

# Reused from the Module 8 status-parsing approach: extract a standardized
# outcome label from the free-text status field (e.g. "Rejected on Jun 02").
OUTCOME_KEYWORDS = {
    "Accepted": "Accepted",
    "Rejected": "Rejected",
    "Waitlisted": "Waitlisted",
    "Wait Listed": "Waitlisted",
    "Interviewed": "Interviewed",
    "Interview": "Interviewed",
}


def parse_outcome(status_str):
    """Extract a standardized applicant_status label from status text."""
    if not isinstance(status_str, str) or status_str.strip() == "":
        return None
    for key, val in OUTCOME_KEYWORDS.items():
        if key.lower() in status_str.lower():
            return val
    return None


def to_string_or_none(value):
    """Convert a numeric value to its string form, preserving nulls."""
    if pd.isna(value):
        return None
    return str(value)


def main():
    """Convert the raw dataset and write the JSON-Lines output file."""
    raw_df = pd.read_json("llm_extend_applicant_data.json")

    records = []
    for _, row in raw_df.iterrows():
        records.append(
            {
                "gpa": to_string_or_none(row.get("GPA")),
                "gre": to_string_or_none(row.get("GRE")),
                "gre_v": to_string_or_none(row.get("GRE V")),
                "gre_aw": to_string_or_none(row.get("GRE AW")),
                "masters_or_phd": row.get("Degree") if pd.notna(row.get("Degree")) else None,
                "citizenship": row.get("US/International")
                if pd.notna(row.get("US/International"))
                else None,
                "applicant_status": parse_outcome(row.get("status")),
            }
        )

    with open("applicant_data.jsonl", "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"Wrote {len(records)} records to applicant_data.jsonl")


if __name__ == "__main__":
    main()
