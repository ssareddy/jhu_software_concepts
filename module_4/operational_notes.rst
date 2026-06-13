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

The ``applicants`` table has a ``UNIQUE`` constraint on the ``url`` column.
All inserts use ``ON CONFLICT (url) DO NOTHING``, so re-running a pull
with previously-seen data is a no-op for those rows.

Uniqueness Key
--------------

Each Grad Café result page has a unique ``/result/<id>`` URL.
This URL is the idempotency key — it is scraped, stored in ``url``, and
enforced at the database level.

Troubleshooting
---------------

**Tests fail with "could not connect to server"**

Ensure PostgreSQL is running and ``DATABASE_URL`` is set::

    export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/gradcafe_test"
    createdb gradcafe_test

**Coverage under 100%**

Run with ``--cov-report=term-missing`` to identify uncovered lines, then
add tests targeting those branches.

**GitHub Actions: service not ready**

The workflow uses ``pg_isready`` health checks with 5 retries.
If Postgres still isn't ready, increase ``health-retries`` in
``.github/workflows/tests.yml``.

**Scraper rate-limited in CI**

All tests inject a fake loader — no live scraping occurs in the test suite.
If you run the real scraper locally and hit rate limits, the scraper will
pause automatically (see ``RATE_LIMIT_PAUSE`` in ``scrape.py``).
