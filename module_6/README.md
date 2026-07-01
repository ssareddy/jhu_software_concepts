# Module 6 — Grad Café Analytics: Microservice Architecture

A production-like microservice version of the Grad Café analytics service,
refactored from Module 5 into four containerized services orchestrated via
Docker Compose: a Flask web app, a Python worker, PostgreSQL, and RabbitMQ.

---

## Architecture Overview

```
module_6/
├── docker-compose.yml                     # Defines all 4 services
├── db/
│   └── init.sql                           # DB schema auto-initialized on start
├── src/
│   ├── web/                               # Flask web service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── run.py                         # Flask entrypoint (0.0.0.0:8080)
│   │   ├── publisher.py                   # RabbitMQ publisher
│   │   └── app/
│   │       ├── app.py                     # Flask app factory
│   │       ├── clean.py                   # ETL data cleaner
│   │       ├── db_config.py               # DB connection config
│   │       ├── query_data.py              # Analysis queries
│   │       └── templates/index.html       # Analysis dashboard
│   ├── worker/                            # Python worker service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── consumer.py                    # RabbitMQ consumer (acks, prefetch=1)
│   │   └── etl/
│   │       ├── incremental_scraper.py     # Selenium scraper
│   │       ├── clean.py                   # ETL data cleaner
│   │       ├── db_config.py               # DB connection config
│   │       └── query_data.py              # Analysis queries
│   ├── db/
│   │   └── load_data.py                   # JSON → PostgreSQL loader
│   └── data/
│       └── llm_extend_applicant_data.json # Cleaned applicant data
├── tests/                                 # Full test suite
├── .github/workflows/ci.yml              # GitHub Actions CI
├── .env.example                           # Environment variable template
├── .coveragerc                            # Coverage configuration
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Services & Ports

| Service    | Port  | Description |
|------------|-------|-------------|
| `web`      | 8080  | Flask analysis dashboard |
| `rabbitmq` | 15672 | RabbitMQ management UI (guest/guest) |
| `db`       | 5433  | PostgreSQL (external access via host) |
| `worker`   | —     | Background task processor |

---

## Docker Hub Registry

Images are publicly available at:

```bash
docker pull scharfshutzer/module_6:web
docker pull scharfshutzer/module_6:worker
```

Registry: https://hub.docker.com/r/scharfshutzer/module_6

---

## Prerequisites

- Docker Desktop (Windows/macOS) or Docker Engine + Docker Compose plugin (Linux)
- Python 3.11+ (for running tests and load_data.py locally)

Verify Docker is working:
```bash
docker run hello-world
docker compose version
```

---

## Quick Start (Docker Compose)

```bash
# 1. Navigate to module_6
cd module_6

# 2. Copy environment file and set credentials
cp .env.example .env
# Edit .env with your values — DATABASE_URL must use 'db' as host inside Docker

# 3. Start all four services
docker compose up --build

# 4. Seed the database (first time only — run in a separate terminal)
export DATABASE_URL="postgresql://postgres:<password>@localhost:5433/gradcafe"
python src/db/load_data.py

# 5. Visit the app
# Web dashboard: http://localhost:8080
# RabbitMQ UI:   http://localhost:15672  (guest / guest)
```

To stop all services:
```bash
docker compose down
```

To reset the database volume completely:
```bash
docker compose down -v
docker compose up --build
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your credentials. Never commit `.env`.

| Variable | Description |
|---|---|
| `POSTGRES_USER` | PostgreSQL superuser |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | Database name |
| `DATABASE_URL` | Full connection string — use `db` as host inside Docker, `localhost:5433` from host machine |
| `RABBITMQ_URL` | RabbitMQ AMQP URL — use `rabbitmq` as host inside Docker |
| `FLASK_ENV` | Flask environment (`development` / `production`) |
| `SEED_JSON` | Path to JSON data file inside worker container |

**Important:** When running `load_data.py` from your host machine, use `localhost:5433`
(the exposed port). Inside Docker containers, services communicate using their service
names (`db:5432`, `rabbitmq:5672`).

---

## How It Works

### Button Flow
1. User clicks **Pull Data** or **Update Analysis** in the browser
2. Flask (`web`) calls `publish_task()` → publishes a message to RabbitMQ exchange `tasks`
3. Flask immediately returns **HTTP 202** with `{status: "queued"}`
4. Worker (`worker`) receives the message via `consumer.py`, processes it, commits to DB, acks

### Task Types
| Task | Handler | What it does |
|---|---|---|
| `scrape_new_data` | `handle_scrape_new_data` | Scrapes GradCafe, cleans, inserts with watermark |
| `recompute_analytics` | `handle_recompute_analytics` | Refreshes materialized views, re-runs queries |

### Watermark Table
The `ingestion_watermarks` table tracks the last seen record per source, enabling
incremental/idempotent loads:
```sql
CREATE TABLE ingestion_watermarks (
    source     TEXT PRIMARY KEY,
    last_seen  TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Running Pylint

Set the Python path first so Pylint can resolve internal imports:

```bash
# Linux / macOS
export PYTHONPATH="module_6/src/web:module_6/src/web/app:module_6/src/worker:module_6/src/worker/etl:module_6/src/db"

# Windows (PowerShell)
$env:PYTHONPATH="module_6/src/web;module_6/src/web/app;module_6/src/worker;module_6/src/worker/etl;module_6/src/db"
```

Then run from the **repo root**:
```bash
pylint module_6/src/web/app/app.py module_6/src/web/publisher.py \
  module_6/src/worker/consumer.py module_6/src/worker/etl/query_data.py \
  module_6/src/worker/etl/clean.py module_6/src/worker/etl/db_config.py \
  module_6/src/db/load_data.py \
  --rcfile=module_6/.pylintrc --fail-under=10
```

Expected: `Your code has been rated at 10.00/10`

---

## Running Tests

From the **repo root**:

```bash
# Set test database URL
export DATABASE_URL="postgresql://postgres:<password>@localhost:5432/gradcafe_test"

# Run full test suite
pytest module_6/tests -m "web or buttons or analysis or db or integration"
```

### With coverage
```bash
pytest module_6/tests -m "web or buttons or analysis or db or integration" \
  --cov-config=module_6/.coveragerc --cov-report=term-missing
```

### Save coverage summary
```bash
pytest module_6/tests -m "web or buttons or analysis or db or integration" \
  --cov-config=module_6/.coveragerc --cov-report=term-missing -q \
  2>&1 | tee module_6/coverage_summary.txt
```

### Test markers

| Marker | Description |
|---|---|
| `web` | Flask route/page rendering and app.py branch tests |
| `buttons` | Pull Data / Update Analysis RabbitMQ publish tests |
| `analysis` | Label presence, percentage formatting tests |
| `db` | Database schema, inserts, idempotency, query function |
| `integration` | End-to-end DB + publish flow tests |

---

## Coverage Notes

The following files are omitted from coverage measurement:

- `src/worker/etl/clean.py`
- `src/worker/etl/db_config.py`
- `src/worker/etl/query_data.py`
- `src/worker/etl/incremental_scraper.py`
- `src/web/app/db_config.py`

**Reason:** Docker containers have isolated filesystems. The `web` and `worker`
services each require their own copy of shared modules because `COPY . .` in
each Dockerfile only copies files within that service's directory. These files
are identical copies of their counterparts in `src/web/app/` and `src/db/`,
which are fully covered by the test suite. `incremental_scraper.py` requires
a live Selenium browser and network access, making it untestable in a unit
test environment.

---

## GitHub Actions CI

Workflow: `.github/workflows/module_6_ci.yml`

The pipeline runs on every push and PR touching `module_6/**` with two jobs:
1. **pylint** — runs Pylint on all module_6 source files, fails if score < 10
2. **pytest** — runs full test suite with 100% coverage enforcement against PostgreSQL 16

See `actions_success.png` for proof of a green run.

---

## Notes for Graders

- All long-running work flows through RabbitMQ — Flask returns 202 immediately
- Worker uses `prefetch_count=1` for backpressure, acks only after DB commit
- On handler error: DB rolls back, message nacked with `requeue=False` (no infinite retries)
- `ingestion_watermarks` table ensures idempotent incremental loads
- No credentials are hard-coded — all read from environment variables
- `.env` is excluded from version control via `.gitignore`
- Docker images publicly available at `scharfshutzer/module_6`
- Database schema is auto-initialized via `db/init.sql` on first `docker compose up`
- DB exposed on port 5433 externally to avoid conflict with local PostgreSQL on 5432