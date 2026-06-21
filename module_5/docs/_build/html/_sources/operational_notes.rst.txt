Operational Notes
=================

Busy-State Policy
-----------------

The app uses a module-level boolean ``_scrape_running`` guarded by a
``threading.Lock``.

* ``POST /api/pull_data`` sets the flag to ``True`` and starts a background
  thread.  If the flag is already ``True`` it returns **409**.
* ``POST /api/update_analysis`` checks the flag; if ``True`` it returns
  **409** and performs no DB query.
* The background thread always clears the flag in a ``finally`` block, even
  on error, so a failed scrape never permanently locks the system.

Idempotency Strategy
--------------------

Every row is assigned a ``content_hash`` (SHA-256 of ``program``, ``status``,
``date_added``, and ``url``) at insert time.  This is the primary dedup key:

.. code-block:: sql

    ON CONFLICT (content_hash) DO NOTHING

This means:

* Records with a valid URL are deduplicated by *both* ``content_hash`` and
  ``url`` (the ``url`` column also carries a UNIQUE constraint).
* Records whose URL is missing or malformed are still deduplicated by their
  content — they never silently accumulate on repeated pulls.
* Completely empty records (no program, status, or URL) are skipped with a
  logged warning before reaching the database.

Connection Configuration
------------------------

All database credentials are resolved from the environment — no hard-coded
passwords anywhere.  ``db_config.py`` is the single source of truth:

.. list-table::
   :header-rows: 1

   * - Variable
     - Description
   * - ``DATABASE_URL``
     - Full connection string (takes priority). E.g. ``postgresql://user:pass@host/db``
   * - ``DB_HOST``
     - Host (default: ``localhost``)
   * - ``DB_PORT``
     - Port (default: ``5432``)
   * - ``DB_NAME``
     - Database name (default: ``gradcafe``)
   * - ``DB_USER``
     - Username (default: ``postgres``)
   * - ``DB_PASSWORD``
     - Password (default: empty — relies on peer/trust auth or ``.pgpass``)

Troubleshooting
---------------

**Tests fail with "could not connect to server"**

Set ``DATABASE_URL`` and ensure the test database exists::

    export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/gradcafe_test"
    createdb gradcafe_test

**Coverage under 100%**

Run with ``--cov-report=term-missing`` to see which lines are uncovered,
then add tests for those branches.

**GitHub Actions: Postgres service not ready**

The workflow uses ``pg_isready`` health checks with 5 retries (10 s interval).
If Postgres still isn't ready, increase ``health-retries`` in
``.github/workflows/tests.yml``.

**Scraper rate-limited**

All tests inject a fake loader — no live scraping in the test suite.
If running the real scraper locally and hitting rate limits, the scraper
pauses automatically (see ``RATE_LIMIT_PAUSE`` in ``scrape.py``).
