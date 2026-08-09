"""
db_config.py
------------
Single source of truth for database connection configuration.

Resolution order (first match wins):
  1. DATABASE_URL environment variable  (e.g. CI / Heroku / Docker)
  2. Individual DB_* environment variables
  3. Safe localhost defaults (no password — relies on peer/trust auth or .pgpass)

Never hard-codes credentials. No interactive prompts.

Usage:
    from db_config import get_db_config, get_connection

    conn = get_connection()          # uses env vars automatically
    config = get_db_config()         # returns a dict for psycopg2.connect(**config)
"""

import os
import urllib.parse
import psycopg2


def get_db_config() -> dict:
    """
    Build a psycopg2-compatible connection dict from the environment.

    Checks DATABASE_URL first (standard for cloud/CI environments),
    then falls back to individual DB_HOST / DB_PORT / DB_NAME /
    DB_USER / DB_PASSWORD variables, then to safe localhost defaults.

    Returns
    -------
    dict
        Keys: host, port, dbname, user, password
    """
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        parsed = urllib.parse.urlparse(database_url)
        return {
            "host":     parsed.hostname or "localhost",
            "port":     parsed.port or 5432,
            "dbname":   parsed.path.lstrip("/") or "gradcafe",
            "user":     parsed.username or "postgres",
            "password": parsed.password or "",
        }

    return {
        "host":     os.environ.get("DB_HOST", "localhost"),
        "port":     int(os.environ.get("DB_PORT", "5432")),
        "dbname":   os.environ.get("DB_NAME", "gradcafe"),
        "user":     os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


def get_connection() -> "psycopg2.connection":
    """
    Open and return a psycopg2 connection using ``get_db_config()``.

    Raises
    ------
    psycopg2.OperationalError
        If the database cannot be reached with the resolved config.
    """
    config = get_db_config()
    return psycopg2.connect(**config)
