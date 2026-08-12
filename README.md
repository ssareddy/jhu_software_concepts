# jhu_software_concepts

Repository for projects and assignments for the course **Modern Software
Concepts in Python** (JHU EN.605.256).

**Author:** Saishrithik Sareddy

## About This Repository

This repository contains my complete body of work for the semester,
spanning web scraping, data cleaning, SQL and PostgreSQL, Flask web
development, containerization, cloud computing (AWS), data visualization
and dashboards, MLOps and experiment tracking, a from-scratch neural
network, and fine-tuned language model deployment. Each module lives in
its own top-level folder (`module_1` through `module_13`), and the final
project (`module_14`) consolidates, corrects, and presents that work as a
finished portfolio.

## Final Portfolio Website

The personal website originally built in Module 1 (`module_1/`) has been
updated into a complete semester portfolio. Its Projects page
(`/projects`) dynamically renders one content block per module, with a
title, a short overview, a personal "what I learned" reflection, and a
link to that module's GitHub folder. All of it is driven entirely by a
single JSON data file, [`projects.json`](./projects.json), at the root
of this repository. The Flask route (`module_1/board/pages.py`) loads
that file at request time and passes it to the `projects.html` template,
so updating the portfolio never requires touching HTML directly.

Run it locally with:

```bash
cd module_1
python run.py
```

Then visit `http://localhost:8080/projects`.

## Repository Organization

| Folder       | Module                                         | Summary                                                                                                                                                                                                                                                     |
|--------------|------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `module_1/`  | Personal Website                               | Flask + Blueprints personal site: About, Projects, Contact pages, later extended into the final portfolio described above.                                                                                                                                  |
| `module_2/`  | Web Scraping                                   | Scraped 30,000+ Grad Cafe admissions entries with Selenium/BeautifulSoup, standardized program/university names with a self-hosted local LLM.                                                                                                               |
| `module_3/`  | SQL Queries and Flask Integration              | Loaded the cleaned Grad Cafe dataset into PostgreSQL and wrote SQL queries answering required admissions questions, displayed through a small Flask page, with portable environment-variable-based database configuration and duplicate-safe inserts.       |
| `module_4/`  | Testing, CI/CD & Documentation                 | Full pytest suite (page rendering, button/busy-state behavior, database inserts, formatting, end-to-end integration) at genuine 100% coverage, GitHub Actions CI with a live Postgres service, and Sphinx documentation published to Read the Docs.         |
| `module_5/`  | Software Assurance + Secure SQL (SQLi Defense) | Hardened the Flask + PostgreSQL application against SQL injection: audited all database queries, migrated to parameterized queries, wired a safe query to a real `/api/search` route, and verified it against real injection payloads with dedicated tests. |
| `module_6/`  | Containerized Analysis Website                 | Docker Compose deployment of the Grad Cafe analysis site: Flask web service, PostgreSQL, and a RabbitMQ-backed worker for scraping/ETL.                                                                                                                     |
| `module_7/`  | Cloud Computing Assignment                     | Established AWS cloud infrastructure: connected S3 and SageMaker via boto3, and deployed the containerized Module 6 application to a live EC2 instance via Docker Compose, with IAM users configured for MFA.                                               |
| `module_8/`  | AWS SageMaker Data Pipeline                    | Cloud-based data cleaning and statistical analysis (hypothesis tests, correlations, contingency analysis) on the Grad Cafe dataset.                                                                                                                         |
| `module_9/`  | KMeans Clustering                              | TF-IDF + PCA clustering of graduate program names, with an elbow analysis and animated Plotly visualizations.                                                                                                                                               |
| `module_10/` | Diamonds Dashboard                             | Interactive Plotly Dash dashboard analyzing diamond pricing against physical features.                                                                                                                                                                      |
| `module_11/` | MLOps Tracking                                 | MLflow and Weights & Biases experiment tracking added to the Module 9 clustering pipeline.                                                                                                                                                                  |
| `module_12/` | Two-Layer Neural Network                       | Admissions classifier built entirely from scratch in NumPy (forward/backward propagation, no ML framework).                                                                                                                                                 |
| `module_13/` | Language Model Deployment                      | Fine-tuned DistilBERT admissions classifier, deployed as a live "Will You Get In?" Flask page.                                                                                                                                                              |
| `module_14/` | Final Portfolio                                | This consolidation: grader-feedback corrections, the updated portfolio website, and these root-level files.                                                                                                                                                 |

## Grader Correction Log

> **Status:** All modules with grader feedback (2–13) are fully reviewed,
> verified, and resolved below. Module 1 had no grader feedback to
> address.

### Module 2 – Web Scraping Assignment

**Grader Comment:** Acceptance/rejection dates were often wrong (13,512 rows
where the status-note date differed from the recorded decision date);
semester and GPA/GRE fields were always null (0/30,000 populated);
`llm_extend_applicant_data.json` was invalid JSONL rather than valid JSON,
contained only 561 rows, and every `llm-generated-program`/
`llm-generated-university` value was empty/"Unknown" due to a
`program`/`program_name` field-name mismatch in `llm_hosting/app.py`;
`requirements.txt` was split/incomplete and the README's run instructions
were unclear.

**Revision Made:** Verified all four areas against the actual current code
and output, not assumed. term/GPA/GRE now populate at realistic rates
(100%/60%/8%) matching every later module's dataset, decision dates are
correctly parsed from status text independent of the raw submission date,
and the LLM output is a valid single JSON array with all 30,000 rows and
correctly populated fields. `requirements.txt` is a single complete file
covering all three source files' actual imports. While reviewing, also
found and fixed two additional issues: a stale filename reference
(`incremental_scraper.py`, left over from a rename, appearing in the
README and in code comments/docstrings across `scrape.py` and `clean.py`)
that would have broken anyone following the README literally, and two
blocks of dead/orphaned code (an unused, more-robust date parser in
`clean.py`, and a duplicated function body wedged inside an unrelated
function in `llm_hosting/app.py`).

**Why it improved the solution:** These four areas accounted for the
majority of the module's original point loss. All four are now verified,
not assumed, fixed, matching the real, populated dataset used throughout
every later module this semester.

---

### Module 3 – SQL Queries and Flask Integration

**Grader Comment:** Connection configuration was inconsistent across
files. `load_data.py` prompted for a password if blank, while
`query_data.py` hardcoded a real, plaintext password directly in source;
local execution failed because the code assumed a `postgres` role/database
setup that isn't guaranteed to exist. Separately: `p_id` is a
sequential, database-generated ID rather than a source-stable one, and
duplicate protection depends entirely on `url` being present and unique.
`ON CONFLICT (url) DO NOTHING` could silently allow duplicate inserts
if a `url` were ever missing or malformed.

**Revision Made:** Built a single shared `db_config.py` module (used
consistently by `load_data.py`, `query_data.py`, and `app.py`) that reads
connection settings from environment variables or a `.env` file, with a
secure runtime password prompt as a fallback. The hardcoded plaintext
password was removed entirely. Added `.env.example` and rewrote the
README's database-setup section around it. Added explicit validation to
skip rows with a missing/empty `url` before insert, in both
`load_data.py` and `app.py` (Postgres allows multiple `NULL`s under a
`UNIQUE` constraint, so this was a genuine gap, not just a style note).
While reviewing, also found and fixed a real Windows-portability bug
(`signal.SIGKILL` does not exist on Windows, silently swallowed by a
broad `except`) and the same stale `incremental_scraper.py` filename
issue found in Module 2. Completed a full pylint cleanup pass across all
6 source files (all now 10.00/10), with every refactor verified against
the actual code behavior, not just re-linted.

**Why it improved the solution:** The hardcoded password is gone from
source entirely, connection setup is now portable across machines, and
the duplicate-protection gap the grader flagged is now actually closed
rather than just noted.

---

### Module 4 – Testing, CI/CD & Documentation

**Grader Comment (96/100):** One busy-state test used `time.sleep(...)`
instead of a deterministic wait; the loader-failure test mainly checked
that the busy flag reset rather than a full route-level/no-partial-write
failure path; the integration test verified `/api/results` more than the
actual rendered `/analysis` page after an update; `scrape.py` was
explicitly excluded from coverage via `# pragma: no cover` on its
Selenium-dependent functions, so the reported 100% coverage wasn't
genuinely across all of `src/`.

**Revision Made:** Confirmed the `time.sleep()` issue was already
resolved before this review (the test suite now exclusively uses
`threading.Event().wait()`). Added a new test that runs the real
scrape→clean→insert pipeline against an actual PostgreSQL database,
forces a failure between scraping and the DB insert, and verifies zero
rows are written (the pipeline's single `execute_values()` + `commit()`
at the very end genuinely prevents partial writes) and that `/api/results`
still returns 200 afterward. Rewrote the integration test: since
`/analysis` is a server-rendered static shell with all data populated
client-side via JavaScript (confirmed by reading the template directly),
Flask's test client cannot literally verify rendered values. Instead the
test now verifies the page is genuinely wired to display the update (the
results-container element, both buttons, and the exact `fetch("/api/results")`
call the page's own script makes). Removed 5 of the 6 pragma exclusions
from `scrape.py` (keeping only the standard `__main__` exclusion) and
wrote roughly 20 new tests, all mocked with no live browser or network
access, covering `check_robots_txt`, `_build_driver`, `_get_page_source`,
`_safe_quit`, and `scrape_data`. Also completed a full pylint cleanup
pass across all 6 source files and all 8 test files, per your request.

**Why it improved the solution:** Coverage is now honest. 100% genuinely
spans all of `src/`, including the previously-excluded scraper, verified
against a real database rather than assumed from a green checkmark.

---

### Module 5 – Software Assurance + Secure SQL (SQLi Defense)

**Grader Comment:** Most dashboard queries remain raw SQL strings, and
malicious-input handling is not clearly demonstrated through explicit
tests (-2). Also flagged: pylint suppressions present in `scrape.py` and
`app.py` despite a reported 10.00/10 score; `setup.py` used
`find_packages(where="src")` against flat top-level `.py` files, risking
a broken package install; `.gitignore` missing from the submission;
`coverage_summary.txt` appeared stale.

**Revision Made:** Confirmed the assignment's actual requirement is
narrower than the grader's comment might suggest: it requires updating
queries that *use user input*, and requires endpoints to *handle
malicious input safely*. The ~20 dashboard queries use only hardcoded
literals, so they were never actually in scope. The real, required gap
was that `get_filtered_results()`, the one query already using the
safe `sql.SQL`/`Identifier` pattern, existed but wasn't reachable from
any Flask route, so there was no endpoint accepting user input for
malicious-input handling to be demonstrated against in the first place.
Wired it to a new `/api/search` route (with dependency injection support,
consistent with how `scraper_fn`/`loader_fn`/`query_fn` are injected
elsewhere in the codebase), and wrote a dedicated test file exercising
it with real SQL-injection-style payloads (`'; DROP TABLE applicants; --`,
`' OR '1'='1`, UNION-based exfiltration attempts, and more) against a
real PostgreSQL database, confirming each payload is treated as a
literal search string, matches zero rows, and never drops or exposes the
table. Also fixed: verified pylint suppressions were already removed
(genuine 10.00/10), verified `setup.py` already used the correct
`py_modules` approach and installs cleanly in a fresh virtual
environment, added the missing `.gitignore`, and found and fixed a stale
`incremental_scraper.py` filename reference in the README (the same
class of bug found independently in Modules 2 and 3).

**Why it improved the solution:** The codebase now has a real,
user-reachable endpoint demonstrating safe handling of malicious input,
not just a parameterized query sitting unused, verified with 24 tests
covering a representative range of real injection techniques, all
passing against an actual database rather than mocked.

---

### Module 6 – Containerized Flask + PostgreSQL Analysis Website

**Grader Comment:** Several categories with minor-to-moderate deductions:
extra build artifacts (`.env`, `__pycache__`, `.pytest_cache`, `.coverage`)
included in the submission; Dockerfiles used loose `>=` version ranges
instead of pinned dependencies; the RabbitMQ publisher's exception
handling was too narrow, so publish failures might not reliably return
the expected 503; the worker didn't catch all possible handler
exceptions for rollback/nack; most significantly, the watermark table
was read but not actually used to filter for newer records (so the
"incremental" scrape wasn't actually incremental), and
`recompute_analytics` only refreshed an existing materialized view with
no clearly created UI-facing table; build/run verification evidence
didn't clearly show both required tasks completing; CI coverage scope
was incomplete.

**Revision Made:** Built a shared `gradcafe_common` package, deduplicating
`query_data.py`, `clean.py`, `db_config.py`, and `amqp.py` across the web
and worker services (using `sys.modules` aliasing shims to preserve
backward-compatible import paths). Fixed a real, previously-undetected
bug in the watermark filter: `date_added` values were being compared as
raw strings (`"Jun 06, 2026"`), which does not sort chronologically for
month names (`"Feb 01, 2026" < "Jan 01, 2026"` lexicographically).
Replaced with proper date parsing before comparison, so the watermark
filter now genuinely limits work to newer records. Fixed the RabbitMQ
exception handling gap: `pika.exceptions.AMQPConnectionError` inherits
directly from `Exception`, not `OSError`/`RuntimeError`, so it was
previously slipping past the except clause entirely and surfacing as an
unhandled 500 instead of the intended 503. Added `pika.exceptions.AMQPError`
to the caught types. Fixed real Docker issues found during review: a
non-root Chromium user crash (needed `useradd --create-home`), a missing
Chrome/chromedriver install in the worker Dockerfile, and the same
Windows-portability `SIGKILL`→`SIGTERM` issue found in later modules.
Achieved genuine 100% test coverage, including a full mocked Selenium
test suite for the scraper (no live browser/network). Fixed the CI
workflow (missing `pip install -e` for the shared package, incorrect
`PYTHONPATH`, missing `setuptools`), and tightened an `.pylintrc` that
had quietly raised thresholds (`max-locals=30`, `min-similarity-lines=500`)
back toward defaults now that the underlying code no longer needs the
loophole.

**Why it improved the solution:** Several of these were genuine
functional bugs, not just style issues. The watermark bug meant the
"incremental" scraper was silently doing full re-scrapes every time, and
the exception-handling gap meant a RabbitMQ outage would crash with a
raw 500 instead of the clean, documented 503 response.

---

### Module 7 – Cloud Computing Assignment

**Grader Comment:** The `dailyWork-SS` IAM user had console access
enabled without MFA (-2). Separately, the deployed EC2 stack was
reachable and rendered correctly, but every analysis answer showed 0.
The database was empty because the `worker` service's Docker Compose
configuration referenced a seed file path (`SEED_JSON=/data/...`)
without a corresponding `volumes:` mount, so the seed data never reached
the container (-5).

**Revision Made:** Enabled MFA on the `dailyWork-SS` IAM user directly in
the AWS Console, confirmed via a fresh screenshot showing "Console
access: Enabled with MFA." Fixed the missing `volumes: - ./data:/data:ro`
mount in the EC2 Docker Compose file, matching the same pattern already
working in Module 6's local compose file, and verified the deployed
application now shows real, non-zero analysis results end-to-end.

**Why it improved the solution:** The deployed EC2 stack now actually
serves real analysis data instead of an empty shell, and the IAM
configuration meets the course's security requirements.

---

### Module 8 – AWS SageMaker Data Pipeline

**Grader Comment (98.5/100):** `decision_date` was only parsed for
Accepted/Rejected outcomes, leaving Interviewed/Waitlisted rows with a
visible date in the status text unparsed; invalid `US/International`
values were set to `NaN` rather than restricted to the three valid
categories; `decision_speed` bucketed negative day counts into
`"0-30 days"`; `application_season` introduced a fourth `"Unknown"`
bucket not present in the assignment's three-category spec.

**Revision Made:** Parse `decision_date` via regex directly from the
`status` text (matching `"<Outcome> on <Mon DD>"`) for all four outcomes,
instead of relying only on the `acceptance_date`/`rejection_date`
columns, which only ever existed for two of the four. Route invalid
`US/International` values to `"Other"` instead of `NaN`. Route negative
`days_to_decision` values to `"Unknown"` instead of `"0-30 days"` (a
negative value means the recorded decision predates the submission date,
a data-quality artifact, not a fast turnaround). Remap
`application_season` so June–August folds into `"Mid Cycle"` rather than
creating an unspecified fourth bucket. Verified all four fixes by
actually re-running the notebook on SageMaker end-to-end: confirmed a
previously-broken case now works correctly (an `"Interview on May 18"`
row now correctly produces `decision_date = 2026-05-18`, which would
previously have been dropped entirely), and specifically checked that
the resulting "100% of rows parsed" figure was genuinely correct rather
than a silently-wrong regex. `status.str.contains('on ')` confirmed
`True` for all 29,831 rows before trusting the parse rate.

**Why it improved the solution:** All four were genuine data-quality or
spec-compliance issues, not cosmetic ones. The `decision_date` fix in
particular recovers real signal (interview/waitlist decision dates) that
was previously silently dropped for every non-Accepted/Rejected row.

---

### Module 9 – KMeans Clustering of Graduate Programs

**Grader Comment (99.5/100):** The initial cluster legend is mislabeled.
Its colors represent sampled clusters 0, 5, 10, …, 45, but the legend
labels them as Clusters 0–9.

**Revision Made:** `plot_initial_clusters()` now samples cluster IDs
evenly across the full label range (`np.linspace` over the sorted unique
labels, e.g. `[0, 5, 10, 16, 21, ..., 49]` for k=50) rather than using
the first 10 cluster indices, and builds the legend directly from those
real sampled ID values. Both the color (`cmap(norm(lbl))`, correctly
normalized against the true min/max label range) and the displayed text
(`f"Cluster {lbl}"`) now use the actual sampled cluster number, so the
legend can never show a different range than the colors it's paired
with. Verified by actually running the function against synthetic data
matching the real k=50 clustering (confirmed the sampled IDs land at
`[0, 5, 10, 16, 21, 27, 32, 38, 43, 49]`, matching the grader's exact
observed pattern) and rendering the real output image to visually
confirm ten distinct, correctly-labeled colors with no overlap.

**Why it improved the solution:** The legend now accurately represents
what it claims to represent: a genuine, verifiable mapping from color
to real cluster ID, not a mismatched placeholder range.

---

### Module 10 – Interactive Diamonds Pricing Dashboard

**Grader Comment:** The dashboard's conclusion text claimed diamond
grade shows "a clear monotonic premium" across cut/color/clarity, which
the actual data doesn't support.

**Revision Made:** Verified against the real correlation computation:
`_monotonic_grades()` correctly returns an empty list when run against
the actual `diamonds.csv` (none of cut/color/clarity are strictly
monotonic in price-per-carat), and `build_conclusion_text()` correctly
falls back to the honest "shifts average price, though not in a strictly
monotonic step" wording. Confirmed this fix was already applied to the
code; regenerated and verified `dashboard.png` reflects the corrected
text, matching the real computed r = 0.92 correlation and all four
required visualizations rendering correctly.

**Why it improved the solution:** The dashboard's stated conclusion now
accurately reflects what the underlying data actually shows, rather than
overstating a pattern that isn't really there.

---

### Module 11 – MLOps Tracking for the KMeans Pipeline

**Grader Comment (99/100 + 5/5 extra credit):** `cluster_details.png`
showed the `inertia` metric but cropped out the `n_init` and
`random_state` parameter values, so the screenshot didn't visibly verify
all four required parameters.

**Revision Made:** Re-ran the real pipeline against a live local MLflow
server and captured a fresh, full-page screenshot showing all four
required parameters (`max_iter`, `n_clusters`, `n_init`, `random_state`)
fully visible alongside the `inertia` metric, matching the assignment's
reference layout.

**Why it improved the solution:** The screenshot now actually
demonstrates what the rubric asks it to demonstrate.

---

### Module 12 – Two-Layer Neural Network From Scratch

**Grader Comment:** The README states no dataset file is included; since
`applicant_data.jsonl` is absent, the submitted script cannot be re-run
from the folder as submitted (-2).

**Revision Made:** Confirmed the assignment's own deliverables list and
suggested file structure don't actually require the dataset file. This
was a deliberate, consistent choice carried through to Module 13 as
well. Since the grader's comment raised it directly, added the dataset
back into the folder and updated the README accordingly, then verified
`neural_network.py` actually runs end-to-end against it.

**Why it improved the solution:** The submission is now runnable exactly
as delivered, removing any ambiguity about reproducibility.

---

### Module 13 – Fine-Tuned Language Model Deployment

**Grader Comment:** The blank and completed prediction page screenshots
were included, but the required screenshot of training/evaluation
output was missing (-1).

**Revision Made:** The real training metrics already existed from an
actual completed run (accuracy 78.95%, precision 76.40%, recall 75.57%,
F1 75.98%, confusion matrix `[[2290,516],[540,1670]]` on 5,016 test
examples, pulled directly from the saved `metadata.json`). This wasn't
new work, just missing visual evidence. Captured and pushed the required
training/evaluation screenshot from that real output.

**Why it improved the solution:** All three required screenshots (blank
page, completed prediction, training/evaluation output) are now present,
each showing genuine output from real runs.

## Final Reflection

**Most challenging module: Module 8 (AWS SageMaker Data Pipeline)**

Cloud work introduced a different kind of difficulty than the purely
local modules. Debugging a notebook running on a SageMaker instance
means every fix has to be re-uploaded, re-run top-to-bottom, and
re-verified against live S3 data before you know if it actually worked.
There's no fast local iteration loop. That showed up directly when
fixing the grader's four flagged issues: `decision_date` was only being
parsed from the `acceptance_date`/`rejection_date` columns, silently
dropping the date for every Interviewed or Waitlisted applicant even
though the same date was sitting right there in the `status` text;
`decision_speed` was bucketing negative day-counts (a data-quality
artifact) into `"0-30 days"` as if they were fast turnarounds; and
`application_season` had an unspecified fourth "Unknown" bucket the
assignment never asked for. Each fix needed a full round-trip back
through SageMaker to confirm, and even after a clean run I had to
specifically double-check that a suspiciously-perfect "100% of rows
parsed" figure was actually correct rather than a silently-wrong regex
matching everything.

**Strongest work: Module 4 (Testing, CI/CD & Documentation)**

This is the module I'd point to as representing a genuinely complete,
professional deliverable, not just working code, but code with real
proof that it works. 210 tests at a genuinely verified 100% coverage
(not just a green badge sitting on top of `# pragma: no cover`
exclusions hiding the untested parts), a GitHub Actions CI pipeline
running against a live PostgreSQL service on every push, and Sphinx
documentation published to Read the Docs. What makes it feel like my
strongest work isn't the coverage number itself. It's that when
`scrape.py`'s Selenium-dependent functions turned out to be excluded
from that coverage, closing the gap meant writing real, fully mocked
tests for browser automation, retry logic, and rate-limit handling, with
no live browser and no network calls, but genuinely exercising every
branch.

**Most improved skill: General software development discipline**

If I had to name one thing, it's the shift from "does this work" to
"can I prove this works, and will it keep working." Concretely: writing
deterministic tests instead of ones that pass most of the time (no
`time.sleep()`-based waits, event-driven synchronization instead),
learning the actual mechanics of mocking well enough to catch subtle
bugs like patching a function at its *definition* when the caller
imported it directly (so the patch silently does nothing), and building
CI pipelines that spin up real service dependencies rather than faking
them. `pytest` and CI/CD specifically went from "not used" to something
I now think of as required infrastructure, not an optional extra.

**How my understanding of Python changed**

I came into this course already fairly experienced with Python, so the
biggest shift wasn't learning new syntax. It was learning to write more
disciplined, maintainable code. Concretely: moving away from catching
`Exception` broadly toward catching the specific exceptions a given
operation can actually raise; treating a pylint warning as a signal to
fix the underlying design rather than suppress it (breaking apart
functions with too many responsibilities instead of raising the
complexity threshold); and understanding *why* certain patterns matter
rather than just following a rule. For example, why deferred imports
inside a function are sometimes the right call for optional dependencies,
but cost you the ability to catch import errors at startup, and why
that tradeoff needs to be made deliberately rather than by default.

## Running Individual Modules

Each `module_N/` folder contains its own `README` (or `README.txt`) and
`requirements.txt` with setup instructions specific to that assignment.
See the root-level [`requirements.txt`](./requirements.txt) for the
combined set of dependencies used across the whole semester.