Testing Guide
=============

Running Marked Tests
--------------------

All tests are marked with one or more of the five pytest markers.

.. code-block:: bash

   # Full suite
   pytest module_4/tests -m "web or buttons or analysis or db or integration"

   # Individual markers
   pytest module_4/tests -m web
   pytest module_4/tests -m buttons
   pytest module_4/tests -m analysis
   pytest module_4/tests -m db
   pytest module_4/tests -m integration

Markers
-------

.. list-table::
   :header-rows: 1

   * - Marker
     - What it covers
   * - ``web``
     - Flask route registration, page load (200), HTML structure
   * - ``buttons``
     - Pull Data / Update Analysis endpoints, busy-state gating
   * - ``analysis``
     - ``Answer:`` label presence, two-decimal percentage formatting
   * - ``db``
     - DB schema, insert, idempotency, ``get_all_results()`` keys
   * - ``integration``
     - End-to-end pull → update → render, duplicate-pull uniqueness

HTML Selectors
--------------

* ``data-testid="pull-data-btn"`` — Pull Data button
* ``data-testid="update-analysis-btn"`` — Update Analysis button

Fixtures (conftest.py)
-----------------------

.. list-table::
   :header-rows: 1

   * - Fixture
     - Scope
     - Description
   * - ``db_conn``
     - session
     - Live psycopg2 connection to ``gradcafe_test``
   * - ``clean_db``
     - function
     - Resets ``applicants`` table before/after each test
   * - ``seeded_db``
     - function
     - ``clean_db`` with ``SAMPLE_RECORDS`` loaded
   * - ``fake_query_fn``
     - function
     - Real ``get_all_results`` patched to use test DB
   * - ``mock_query_fn``
     - function
     - In-memory fake that returns known values
   * - ``app``
     - function
     - Flask app with ``mock_query_fn``, no DB needed
   * - ``client``
     - function
     - Flask test client for ``app``
   * - ``app_with_db``
     - function
     - Flask app wired to live test DB
   * - ``client_with_db``
     - function
     - Flask test client for ``app_with_db``

Test Doubles
------------

Dependency injection is used throughout so no test hits the live internet:

* **Scraper/loader** — injected via ``create_app(loader_fn=...)``.
* **Query function** — injected via ``create_app(query_fn=...)``.
* **Busy state** — inspected via ``GET /api/scrape_status``; no ``sleep()``.
