"""model_common.py - Shared unified-text template for Module 13.

This module is the single source of truth for the text representation
used to convert an applicant's fields into one input string for the
fine-tuned model. It is imported by both train_model.py (training) and
inference.py (standalone reload demo + the Flask "Will You Get In?"
webpage), eliminating any risk of the training and inference-time text
formats drifting apart.

The exact template and value-formatting logic below is unchanged from
what was actually used to produce the saved model in saved_model/, so
importing it here does not require retraining -- this module simply
gives the previously-duplicated logic one canonical home.
"""

import numpy as np
import pandas as pd

UNIFIED_TEMPLATE = (
    "Program: {program}\n"
    "University: {university}\n"
    "Comments: {comments}\n"
    "Term: {term}\n"
    "Degree: {degree}\n"
    "Citizenship: {citizenship}\n"
    "GPA: {gpa}\n"
    "GRE: {gre}\n"
    "GRE Verbal: {gre_v}\n"
    "GRE AW: {gre_aw}"
)


def _format_string_value(raw: str, stripped: str, placeholder: str) -> str:
    """Format a string-typed field value (helper for format_value()).

    Args:
        raw: The original string value.
        stripped: raw with surrounding whitespace removed.
        placeholder: Text to use when the value is missing/unknown.

    Returns:
        placeholder if stripped is empty or literally "unknown"; otherwise
        the numeric-reformatted string if stripped parses as a float
        (matching training-time float formatting); otherwise raw itself.
    """
    if stripped == "" or stripped.lower() == "unknown":
        return placeholder
    try:
        return f"{float(stripped):g}"
    except ValueError:
        return str(raw)


def format_value(val, placeholder: str = "Unknown") -> str:
    """Consistent missing-value and numeric formatting for the template.

    Applied identically at training time (to raw dataset values) and at
    inference time (to values submitted through the Flask form), so the
    model always sees the same text representation for the same
    underlying value. Every branch below matches the exact logic already
    used to produce the saved training data; the only addition is
    routing string values through _format_string_value(), which fixed a
    train/inference formatting mismatch (e.g. a user-submitted "3.90"
    now renders identically to the "3.9" a training-time float of 3.90
    would have produced).

    Args:
        val: A raw field value of any type (None, NaN, str, float, int).
        placeholder: Text to use when val is missing/empty/unknown.

    Returns:
        The formatted, display-ready string.
    """
    if val is None:
        return placeholder
    if isinstance(val, float) and (pd.isna(val) or np.isnan(val)):
        return placeholder
    if isinstance(val, str):
        return _format_string_value(val, val.strip(), placeholder)
    if isinstance(val, float):
        # Numeric field: keep original precision, e.g. GPA 3.87, GRE 168.0 -> 168.
        return f"{val:g}"
    return str(val)


def build_unified_text(record: dict) -> str:
    """Build the single unified text representation for one applicant.

    Args:
        record: A dict with keys "program", "university", "comments",
            "term", "degree", "citizenship", "gpa", "gre", "gre_v",
            "gre_aw". Any key may be missing or None.

    Returns:
        The consistent, human-readable, labeled text block used as model
        input at both training and inference time.
    """
    return UNIFIED_TEMPLATE.format(
        program=format_value(record.get("program")),
        university=format_value(record.get("university")),
        comments=format_value(record.get("comments")),
        term=format_value(record.get("term")),
        degree=format_value(record.get("degree")),
        citizenship=format_value(record.get("citizenship")),
        gpa=format_value(record.get("gpa")),
        gre=format_value(record.get("gre")),
        gre_v=format_value(record.get("gre_v")),
        gre_aw=format_value(record.get("gre_aw")),
    )
