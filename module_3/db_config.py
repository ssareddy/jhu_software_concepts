"""
db_config.py
------------
Single source of truth for the PostgreSQL connection used by
load_data.py, query_data.py, and app.py.

Connection values are read from environment variables so the same code
runs unchanged on any machine (yours, a grader's, a CI runner, etc.):

    DB_HOST      (default: localhost)
    DB_PORT      (default: 5432)
    DB_NAME      (default: gradcafe)
    DB_USER      (default: postgres)
    DB_PASSWORD  (default: "" -- see note below)

If DB_PASSWORD is not set, get_connection() falls back to no password
first (covers local "trust"/peer-auth Postgres setups on Linux, which is
common), and only prompts interactively if that connection attempt
fails. This keeps things working non-interactively in most local and
grading environments while still having a safe manual fallback.
"""

import os
import getpass
import psycopg2


def _config_from_env():
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", "gradcafe"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


def get_connection():
    """Return a psycopg2 connection, built from environment variables.

    Falls back to an interactive password prompt only if DB_PASSWORD is
    unset AND a passwordless connection attempt fails.
    """
    config = _config_from_env()

    try:
        return psycopg2.connect(**config)
    except psycopg2.OperationalError:
        if config["password"]:
            raise
        config["password"] = getpass.getpass(
            f"Enter PostgreSQL password for user '{config['user']}' "
            f"(or set DB_PASSWORD to skip this prompt): "
        )
        return psycopg2.connect(**config)
