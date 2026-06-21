Architecture
============

The system has three layers:

Web Layer (Flask)
-----------------

``app.py`` provides a ``create_app()`` factory that registers five routes:

* ``GET /`` and ``GET /analysis`` — serve the analysis dashboard.
* ``POST /api/pull_data`` — trigger the ETL pipeline in a background thread.
* ``POST /api/update_analysis`` — refresh analysis from the DB.
* ``GET /api/scrape_status`` — check whether a pull is in progress.

The busy-state flag (``_scrape_running``) is guarded by a ``threading.Lock``
so concurrent requests are safe.

ETL Layer
---------

* **scrape.py** — headless Chrome (Selenium) fetches paginated Grad Café
  survey pages; BeautifulSoup/regex parses each record.
* **clean.py** — normalises raw records into a structured schema using pure
  Python string methods and regex; no external services.
* **load_data.py** — bulk-inserts cleaned records into PostgreSQL with
  ``ON CONFLICT (url) DO NOTHING`` to enforce idempotency.

Database Layer
--------------

A single ``applicants`` table in PostgreSQL stores all records.
The ``url`` column carries a UNIQUE constraint, which is the uniqueness key
for all idempotency guarantees.

``query_data.py`` contains the ``get_all_results()`` function that runs all
eleven analytical queries and returns a single dict consumed by the Flask API.
