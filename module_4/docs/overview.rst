Overview & Setup
================

The Grad Café Analytics system scrapes graduate admissions data from
`thegradcafe.com <https://www.thegradcafe.com>`_, cleans and stores it in
PostgreSQL, and presents a Flask analysis dashboard.

Environment Variables
---------------------

.. list-table::
   :header-rows: 1

   * - Variable
     - Default
     - Description
   * - ``DATABASE_URL``
     - ``postgresql://postgres:postgres@localhost:5432/gradcafe_test``
     - PostgreSQL connection string used by the app and tests.

Setup
-----

.. code-block:: bash

   pip install -r module_4/requirements.txt

   # Create databases
   createdb gradcafe
   createdb gradcafe_test

   export DATABASE_URL="postgresql://postgres:<password>@localhost:5432/gradcafe"

Running the App
---------------

.. code-block:: bash

   cd module_4/src
   python app.py
   # Listening at http://localhost:8080

Running Tests
-------------

.. code-block:: bash

   pytest module_4/tests \
     -m "web or buttons or analysis or db or integration" \
     --cov=module_4/src \
     --cov-report=term-missing \
     --cov-fail-under=100
