"""
clean.py (web service)
--------------------------
Module alias, not a plain re-export. Real implementation lives in
gradcafe_common (shared with worker/) — see
src/common/gradcafe_common/clean.py and src/common/setup.py for why.

The explicit import below is functionally redundant (the sys.modules
line replaces this module's identity entirely) — it exists purely so
static analyzers like pylint can see `clean_data` is genuinely defined,
since they can't follow the runtime sys.modules swap.
"""
import sys

from gradcafe_common.clean import clean_data
import gradcafe_common.clean as _real

__all__ = ["clean_data"]

sys.modules[__name__] = _real
