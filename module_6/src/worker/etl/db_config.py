"""
db_config.py (worker service)
-------------------------------
Module alias, not a plain re-export. Real implementation lives in
gradcafe_common (shared with web/) — see
src/common/gradcafe_common/db_config.py and src/common/setup.py for why.

The explicit import below is functionally redundant (the sys.modules
line replaces this module's identity entirely) — it exists purely so
static analyzers like pylint can see these names are genuinely defined,
since they can't follow the runtime sys.modules swap. The swap is what
actually matters at runtime: it makes `import db_config` resolve to the
*exact same module object* as gradcafe_common.db_config, so the test
suite's direct patching (e.g. `patch("db_config.psycopg2.connect", ...)`)
reaches the real implementation.
"""
import sys

from gradcafe_common.db_config import get_db_config, get_connection
import gradcafe_common.db_config as _real

__all__ = ["get_db_config", "get_connection"]

sys.modules[__name__] = _real
