# Module 3 — Grad Café SQL & Flask Analysis

## Overview

This module loads scraped Grad Café data into a PostgreSQL database, runs SQL
queries to answer analysis questions, and displays results on a dynamic Flask
webpage with live data-refresh controls.

---

## Project Structure

```
module_3/
├── scrape.py             # Scrapes applicant data from Grad Café (copied from Module 2)
├── clean.py              # Cleans raw scraped records (copied from Module 2)
├── load_data.py          # Loads JSON data into PostgreSQL
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
- Google Chrome installed (required by Selenium for scraping)
- The cleaned Grad Café JSON data file (`llm_extend_applicant_data.json`)

---

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 2. Database Setup

Create the PostgreSQL database:

```bash
psql -U postgres -c "CREATE DATABASE gradcafe;"
```

---

## 3. Configure Database Credentials

Open `load_data.py` and `query_data.py` and edit the `DB_CONFIG` dict at the
top of each file:

```python
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "gradcafe",
    "user":     "postgres",
    "password": "",          # Leave blank to be prompted, or enter your password here
}
```

If `password` is left as an empty string, you will be securely prompted to
enter it in the terminal when running any script. Alternatively, you can fill
it in directly in the file.

---

## 4. Load Initial Data

Load the cleaned Grad Café JSON file into the database:

```bash
python load_data.py --json llm_extend_applicant_data.json
```

This will:
- Create the `applicants` table with a `UNIQUE` constraint on `url` (prevents duplicates)
- Insert all records from the JSON file, skipping any duplicates

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
| **Pull Data** | Scrapes the most recent pages from Grad Café, cleans the results in memory, and inserts any new entries into the database. Runs in the background; may take several minutes. Duplicate entries are automatically skipped. |
| **Update Analysis** | Re-runs all SQL queries and refreshes the displayed results with the latest data. Disabled while a Pull Data request is in progress. |

---

## 7. How Pull Data Works

When the Pull Data button is clicked, `app.py` runs the following pipeline
entirely in memory (no intermediate files written):

1. `scrape.py` — scrapes the first 10 pages of Grad Café (~200 entries)
2. `clean.py` — cleans and structures the raw records
3. psycopg2 — inserts new records directly into the database, skipping duplicates via `ON CONFLICT (url) DO NOTHING`

---

## 8. Files Submitted

| File | Purpose |
|------|---------|
| `scrape.py` | Grad Café web scraper (Selenium + BeautifulSoup) |
| `clean.py` | Raw record cleaner (regex + string methods) |
| `load_data.py` | Initial database loader |
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
- GRE scores are validated to the 130–170 range and GRE AW to 0–6 to
  filter out any malformed entries before averaging.
- The Pull Data button is safe to click multiple times — simultaneous scrapes
  are blocked and the user is notified via a status banner.