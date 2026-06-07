# Module 3 — Grad Café SQL & Flask Analysis

## Overview

This module loads scraped Grad Café data into a PostgreSQL database, runs SQL
queries to answer analysis questions, and displays results on a dynamic Flask
webpage with live data-refresh controls.

---

## Project Structure

```
module_3/
├── load_data.py          # Load CSV data into PostgreSQL
├── query_data.py         # SQL queries + helpers for Flask
├── app.py                # Flask web application
├── templates/
│   └── index.html        # Webpage template
├── static/
│   └── style.css         # Stylesheet
├── limitations.pdf       # Written reflection on data limitations
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## Prerequisites

- Python 3.9+
- PostgreSQL 14+ installed and running
- Cleaned Grad Café CSV from Module 2

---

## 1. Database Setup

### Local PostgreSQL (Linux/macOS)

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE gradcafe;"
```

### Windows (via pgAdmin or psql prompt)

```sql
CREATE DATABASE gradcafe;
```

---

## 2. Environment Variables

Set these before running any scripts (or edit `DB_CONFIG` directly in each file):

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=gradcafe
export DB_USER=postgres
export DB_PASSWORD=your_password_here
```

On Windows (Command Prompt):

```cmd
set DB_HOST=localhost
set DB_PORT=5432
set DB_NAME=gradcafe
set DB_USER=postgres
set DB_PASSWORD=your_password_here
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Load Data

```bash
python load_data.py --csv path/to/your/cleaned_gradcafe.csv
```

This will:
- Create the `applicants` table if it does not exist
- Insert all rows from the CSV (skipping duplicates)

---

## 5. Run Queries (Console Output)

```bash
python query_data.py
```

Prints answers to all 9 required questions and 2 custom questions to the terminal.

---

## 6. Run the Flask Webpage

```bash
python app.py
```

Open your browser to: **http://localhost:5000**

### Webpage Features

| Button | Description |
|--------|-------------|
| **Pull Data** | Triggers the Module 2 scraper to fetch new Grad Café entries and add them to the database. Runs in the background; may take several minutes. |
| **Update Analysis** | Refreshes all displayed query results with the latest database contents. Disabled while a data pull is in progress. |

---

## 7. Module 2 Scraper Integration

`app.py` calls `../module_2/scraper.py` when "Pull Data" is clicked.
Make sure your Module 2 scraper:
- Accepts no required command-line arguments (or update the path in `app.py`)
- Writes new entries to the same CSV, which `load_data.py` can re-process, **or**
- Directly inserts into the `applicants` table via psycopg2

---

## 8. Files Submitted

| File | Purpose |
|------|---------|
| `load_data.py` | Database loader |
| `query_data.py` | SQL analysis queries |
| `app.py` | Flask application |
| `templates/index.html` | Frontend webpage |
| `static/style.css` | CSS styling |
| `limitations.pdf` | Written reflection on data limitations |
| `requirements.txt` | Package list |
| `README.md` | This document |

---

## Notes

- All SQL queries use `ILIKE` for case-insensitive matching to handle
  inconsistencies in user-submitted text fields.
- LLM-generated fields (`llm_generated_program`, `llm_generated_university`)
  are used in Q7–Q9 to improve matching accuracy.
- The "Pull Data" button is safe to click multiple times — simultaneous scrapes
  are blocked and the user is notified.
