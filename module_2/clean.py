"""
clean.py — Grad Cafe Data Cleaner
-----------------------------------
Converts raw scraped records (produced by scrape.py) into structured,
clean JSON objects using Python string methods and regex.

Note: University and program name standardization is handled separately
by the local LLM in llm_hosting/app.py, which adds llm-generated-program
and llm-generated-university fields to produce llm_extend_applicant_data.json.

Output schema per record
------------------------
{
  "program_name":            str | None,
  "university":              str | None,
  "degree_type":             "PhD" | "Masters" | None,
  "status":                  "Accepted" | "Rejected" | "Waitlisted" | "Interview" | None,
  "decision_date":           str | None,   # ISO-8601 YYYY-MM-DD
  "semester_year":           str | None,   # e.g. "Fall 2024"
  "student_type":            "American" | "International" | None,
  "gpa":                     float | None,
  "gre_total":               int | None,
  "gre_verbal":              int | None,
  "gre_quant":               int | None,
  "gre_aw":                  float | None,
  "comments":                str | None,
  "date_added":              str | None,   # ISO-8601 YYYY-MM-DD
  "url":                     str | None,
  "raw_institution_program": str,          # original text, preserved
  "raw_degree_status":       str,          # original text, preserved
  "raw_date":                str,          # original text, preserved
  "raw_notes":               str,          # original text, preserved
}
"""

import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RAW_FILE   = Path("raw_results.json")
CLEAN_FILE = Path("applicant_data.json")

# Mapping common status strings to canonical values
_STATUS_MAP = {
    "accepted": "Accepted",
    "accept": "Accepted",
    "admitted": "Accepted",
    "admission": "Accepted",
    "rejected": "Rejected",
    "reject": "Rejected",
    "denial": "Rejected",
    "denied": "Rejected",
    "waitlisted": "Waitlisted",
    "waitlist": "Waitlisted",
    "wait list": "Waitlisted",
    "interview": "Interview",
    "interviewed": "Interview",
}

_DEGREE_MAP = {
    "phd": "PhD",
    "ph.d": "PhD",
    "doctoral": "PhD",
    "doctorate": "PhD",
    "master": "Masters",
    "ms ": "Masters",
    "m.s": "Masters",
    "ma ": "Masters",
    "m.a": "Masters",
    "mba": "Masters",
    "meng": "Masters",
    "m.eng": "Masters",
}


# ---------------------------------------------------------------------------
# Deterministic field extractors (Python string methods + regex)
# ---------------------------------------------------------------------------

def _normalize_status(text: str) -> str | None:
    """Map raw status text to a canonical decision value."""
    lower = text.lower()
    for key, value in _STATUS_MAP.items():
        if key in lower:
            return value
    return None


def _normalize_degree(text: str) -> str | None:
    """Detect degree type from combined raw text."""
    lower = text.lower()
    for key, value in _DEGREE_MAP.items():
        if key in lower:
            return value
    return None


def _extract_gpa(text: str) -> float | None:
    """
    Extract GPA from notes text. Handles patterns like:
    'GPA: 3.75', 'gpa 3.9', '3.85/4.0', '4.00 GPA'
    """
    patterns = [
        r"gpa[:\s]*([0-4]\.\d{1,2})",
        r"([0-4]\.\d{1,2})\s*/\s*4(?:\.0)?",
        r"([0-4]\.\d{1,2})\s*gpa",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            try:
                val = float(m.group(1))
                if 0.0 <= val <= 4.0:
                    return round(val, 2)
            except ValueError:
                pass
    return None


def _extract_gre(text: str) -> dict[str, Any]:
    """
    Extract GRE scores from notes text. Returns a dict with keys:
    gre_total, gre_verbal, gre_quant, gre_aw
    """
    result: dict[str, Any] = {
        "gre_total": None,
        "gre_verbal": None,
        "gre_quant": None,
        "gre_aw": None,
    }

    # Verbal
    m = re.search(r"gre\s*v(?:erbal)?[:\s]*(\d{3})", text, re.I)
    if m:
        result["gre_verbal"] = int(m.group(1))

    # Quant
    m = re.search(r"gre\s*q(?:uant(?:itative)?)?[:\s]*(\d{3})", text, re.I)
    if m:
        result["gre_quant"] = int(m.group(1))

    # AW / Writing
    m = re.search(r"(?:aw|writing|analytical)[:\s]*([0-6](?:\.[05])?)", text, re.I)
    if m:
        try:
            result["gre_aw"] = float(m.group(1))
        except ValueError:
            pass

    # Total (V+Q combined)
    if result["gre_verbal"] and result["gre_quant"]:
        result["gre_total"] = result["gre_verbal"] + result["gre_quant"]
    else:
        # Fallback: standalone GRE total
        m = re.search(r"gre[:\s]*(\d{3})", text, re.I)
        if m:
            result["gre_total"] = int(m.group(1))

    return result


def _extract_semester_year(text: str) -> str | None:
    """Extract program start semester/year, e.g. 'Fall 2024'."""
    m = re.search(r"(fall|spring|summer|winter)\s*(20\d{2}|19\d{2})", text, re.I)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"
    return None


def _extract_date(text: str) -> str | None:
    """
    Parse a date string into ISO-8601 (YYYY-MM-DD).
    Handles: 'Jan 15, 2024', '01/15/2024', '2024-01-15', 'January 2024'.
    """
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    # ISO format
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # MM/DD/YYYY
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    # Month Day, Year
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if m:
        month_str = m.group(1).lower()
        if month_str in months:
            return f"{m.group(3)}-{months[month_str]:02d}-{int(m.group(2)):02d}"

    # Month Year only
    m = re.search(r"([A-Za-z]+)\s+(20\d{2}|19\d{2})", text)
    if m:
        month_str = m.group(1).lower()
        if month_str in months:
            return f"{m.group(2)}-{months[month_str]:02d}-01"

    return None


def _extract_student_type(text: str) -> str | None:
    """Detect domestic/international student status."""
    lower = text.lower()
    if any(w in lower for w in ("international", "non-us", "non us", "foreign")):
        return "International"
    if any(w in lower for w in ("domestic", "american", "us citizen", "u.s.")):
        return "American"
    return None


def _strip_html(text: str) -> str:
    """Remove residual HTML tags and entities from a string."""
    text = re.sub(r"<[^>]+>", " ", text)
    entities = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    return " ".join(text.split()).strip()


def _split_institution_program(raw: str) -> tuple[str | None, str | None]:
    """
    Split 'University Name - Program Name' style text into
    separate university and program strings.
    """
    raw = _strip_html(raw)
    for sep in (" — ", " - ", " – ", " | "):
        if sep in raw:
            parts = raw.split(sep, 1)
            return parts[0].strip() or None, parts[1].strip() or None
    return raw.strip() or None, None


def _clean_record(raw: dict) -> dict:
    """
    Extract and structure all fields from a single raw scraped record.
    Raw fields are always preserved for traceability.
    """
    combined_text = " ".join(filter(None, [
        raw.get("raw_institution_program", ""),
        raw.get("raw_degree_status", ""),
        raw.get("raw_date", ""),
        raw.get("raw_notes", ""),
    ]))

    university, program_name = _split_institution_program(
        raw.get("raw_institution_program", "")
    )

    return {
        "program_name":            program_name,
        "university":              university,
        "degree_type":             _normalize_degree(combined_text),
        "status":                  _normalize_status(combined_text),
        "decision_date":           _extract_date(raw.get("raw_date", "")),
        "semester_year":           _extract_semester_year(combined_text),
        "student_type":            _extract_student_type(combined_text),
        "gpa":                     _extract_gpa(combined_text),
        "gre_total":               _extract_gre(combined_text)["gre_total"],
        "gre_verbal":              _extract_gre(combined_text)["gre_verbal"],
        "gre_quant":               _extract_gre(combined_text)["gre_quant"],
        "gre_aw":                  _extract_gre(combined_text)["gre_aw"],
        "comments":                _strip_html(raw.get("raw_notes", "")) or None,
        "date_added":              _extract_date(raw.get("raw_date", "")),
        "url":                     raw.get("url") or None,
        # Preserved raw fields for traceability
        "raw_institution_program": raw.get("raw_institution_program", ""),
        "raw_degree_status":       raw.get("raw_degree_status", ""),
        "raw_date":                raw.get("raw_date", ""),
        "raw_notes":               _strip_html(raw.get("raw_notes", "")),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_data(raw_records: list[dict]) -> list[dict]:
    """
    Clean a list of raw scraped records using regex and string methods.

    Args:
        raw_records: Raw records produced by scrape_data() in scrape.py.

    Returns:
        List of cleaned, structured applicant record dicts.
    """
    cleaned = []
    for raw in raw_records:
        cleaned.append(_clean_record(raw))
    print(f"[clean] Done. {len(cleaned):,} records cleaned.")
    return cleaned


def save_data(records: list[dict], path: Path = CLEAN_FILE) -> None:
    """
    Save cleaned applicant records to a valid JSON file.

    Args:
        records: List of cleaned record dicts.
        path:    Output file path (default: applicant_data.json).
    """
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    print(f"[save] {len(records):,} records written to {path}.")


def load_data(path: Path = CLEAN_FILE) -> list[dict]:
    """
    Load cleaned applicant records from applicant_data.json.

    Args:
        path: Path to applicant_data.json.

    Returns:
        List of cleaned record dicts.
    """
    with open(path, encoding="utf-8") as fh:
        records = json.load(fh)
    print(f"[load] {len(records):,} records loaded from {path}.")
    return records


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    with open(RAW_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)
    cleaned = clean_data(raw)
    save_data(cleaned)