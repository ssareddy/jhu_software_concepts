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
(`/projects`) dynamically renders one content block per module — title,
a short overview, a personal "what I learned" reflection, and a link to
that module's GitHub folder — driven entirely by a single JSON data file,
[`projects.json`](./projects.json), at the root of this repository. The
Flask route (`module_1/board/pages.py`) loads that file at request time
and passes it to the `projects.html` template, so updating the portfolio
never requires touching HTML directly.

Run it locally with:

```bash
cd module_1
python run.py
```

Then visit `http://localhost:8080/projects`.

## Repository Organization

| Folder       | Module                                                                                  | Summary                                                                                                                                       |
|--------------|-----------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| `module_1/`  | Personal Website                                                                        | Flask + Blueprints personal site: About, Projects, Contact pages, later extended into the final portfolio described above.                    |
| `module_2/`  | Web Scraping                                                                            | Scraped 30,000+ Grad Cafe admissions entries with Selenium/BeautifulSoup, standardized program/university names with a self-hosted local LLM. |
| `module_3/`  | *TODO — confirm title/summary*                                                          |                                                                                                                                               |
| `module_4/`  | *TODO — confirm title/summary*                                                          |                                                                                                                                               |
| `module_5/`  | *TODO — confirm title/summary (Flask + PostgreSQL analysis site, pre-containerization)* |                                                                                                                                               |
| `module_6/`  | Containerized Analysis Website                                                          | Docker Compose deployment of the Grad Cafe analysis site: Flask web service, PostgreSQL, and a RabbitMQ-backed worker for scraping/ETL.       |
| `module_7/`  | *TODO — confirm title/summary*                                                          |                                                                                                                                               |
| `module_8/`  | AWS SageMaker Data Pipeline                                                             | Cloud-based data cleaning and statistical analysis (hypothesis tests, correlations, contingency analysis) on the Grad Cafe dataset.           |
| `module_9/`  | KMeans Clustering                                                                       | TF-IDF + PCA clustering of graduate program names, with an elbow analysis and animated Plotly visualizations.                                 |
| `module_10/` | Diamonds Dashboard                                                                      | Interactive Plotly Dash dashboard analyzing diamond pricing against physical features.                                                        |
| `module_11/` | MLOps Tracking                                                                          | MLflow and Weights & Biases experiment tracking added to the Module 9 clustering pipeline.                                                    |
| `module_12/` | Two-Layer Neural Network                                                                | Admissions classifier built entirely from scratch in NumPy (forward/backward propagation, no ML framework).                                   |
| `module_13/` | Language Model Deployment                                                               | Fine-tuned DistilBERT admissions classifier, deployed as a live "Will You Get In?" Flask page.                                                |
| `module_14/` | Final Portfolio                                                                         | This consolidation: grader-feedback corrections, the updated portfolio website, and these root-level files.                                   |

## Grader Correction Log

> **[In progress.]** This section will list, for each module where feedback
> was provided: the module number and title, a concise paraphrase of the
> grader's comment, the specific change made in response, and why that
> change improved the solution. Being completed module-by-module as each
> is reviewed.

## Final Reflection

> **[Pending.]** A short reflection on the most challenging module, the
> module reflecting my strongest work, the skills I improved most this
> semester, and how my understanding of Python changed from the start of
> the course to the end.

## Running Individual Modules

Each `module_N/` folder contains its own `README` (or `README.txt`) and
`requirements.txt` with setup instructions specific to that assignment.
See the root-level [`requirements.txt`](./requirements.txt) for the
combined set of dependencies used across the whole semester.