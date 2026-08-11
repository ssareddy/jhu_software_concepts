"""
query_data.py (web service)
------------------------------
Module alias, not a plain re-export. The real implementation lives in
gradcafe_common (shared with worker/) — see
src/common/gradcafe_common/query_data.py and src/common/setup.py for why.

The explicit `from gradcafe_common.query_data import ...` line below is
functionally redundant (the sys.modules line after it replaces this
module's identity with the real one entirely) — it exists purely so
static analyzers like pylint can see these names are genuinely defined,
since they can't follow the runtime sys.modules swap. The swap is what
actually matters at runtime: it makes `import query_data` / `from
app.query_data import ...` resolve to the *exact same module object* as
gradcafe_common.query_data, so the test suite's direct patching of
internals (e.g. `patch("query_data.psycopg2.connect", ...)`, calling
`query_data._conn()`) reaches the real implementation.
"""
import sys

from gradcafe_common.query_data import (
    MAX_LIMIT,
    get_filtered_results,
    run_queries,
    get_all_results,
)
import gradcafe_common.query_data as _real

__all__ = ["MAX_LIMIT", "get_filtered_results", "run_queries", "get_all_results"]

sys.modules[__name__] = _real
