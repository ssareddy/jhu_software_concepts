# Module 11 — MLOps Pipeline for Grad Cafe KMeans Clustering

## Purpose

`kmeans_mlops_pipeline.py` reuses the Module 9 Grad Cafe program-clustering
workflow (data loading, cleaning, TF-IDF vectorization, and PCA
dimensionality reduction) and adds MLOps experiment tracking on top of it.
It trains a single scikit-learn KMeans model with a required, fixed set of
clustering parameters, then logs that run's parameters, its `inertia_`
metric, and the trained model itself to [MLflow](https://mlflow.org/) —
and, optionally, to [Weights & Biases](https://wandb.ai/) — so training
runs can be tracked, compared, and revisited later.

## Setup

```bash
pip install -r requirements.txt
```

You'll also need the raw Grad Cafe dataset (`llm_extend_applicant_data.json`,
the same file used in Module 9) in this folder, or pass its path via
`--input`.

## Running the MLflow Version (Required)

**1. Start the MLflow tracking server** in its own terminal, before running
the script:

```bash
mlflow server --host <your IP> --port 8080
```

- If working locally, `<your IP>` can simply be `127.0.0.1` (or
  `localhost`).
- If working on another machine, find your IP first (on Linux/macOS:
  `hostname -I`).
- Once running, the MLflow UI is reachable at `http://<your IP>:8080` in a
  browser.

**2. Run the pipeline**, pointing it at the same host/port the server is
using:

```bash
python kmeans_mlops_pipeline.py \
    --input llm_extend_applicant_data.json \
    --tracking-uri http://127.0.0.1:8080 \
    --tracker mlflow
```

This trains the KMeans model and logs the run to MLflow under the
experiment name `grad_cafe_kmeans_clustering`.

### What Gets Logged

- **Parameters:** `max_iter=500`, `n_clusters=25`, `n_init=5`,
  `random_state=42` (the required clustering configuration for this
  assignment)
- **Metric:** `inertia` — the fitted KMeans model's `inertia_` attribute
- **Model:** the trained KMeans model, logged as an MLflow model artifact
  and registered under the name `Clustering`

### Where to Find Things in the MLflow UI

- **Runs table:** Experiments tab → `grad_cafe_kmeans_clustering` →
  the `kmeans-clustering-run` row (see `cluster_run.png`)
- **Run details (parameters + metric):** click into that run
  (see `cluster_details.png`)
- **Registered model:** Models tab → `Clustering` → Version 1
  (see `model_details.png`)

## Running the Weights & Biases Version (Optional Extra Credit)

The same script can log to wandb instead of (or in addition to) MLflow,
switchable with the `--tracker` flag:

```bash
# wandb only
python kmeans_mlops_pipeline.py --tracker wandb

# both MLflow and wandb in the same run
python kmeans_mlops_pipeline.py --tracker both --tracking-uri http://127.0.0.1:8080
```

Before running the wandb version, set up your own account:

```bash
pip install wandb          # already included in requirements.txt
wandb login                # authenticate with your free wandb.ai account
```

This logs the same `CLUSTER_PARAMS` as the MLflow run, plus the `inertia`
metric, and saves the trained model as a wandb Artifact (named
`kmeans-clustering-model`) under the project `grad-cafe-kmeans-clustering`.

For testing without an account, `--wandb-mode offline` runs the full
pipeline and saves everything locally without requiring authentication;
`--wandb-mode online` (the default) requires `wandb login` first and is
what produces a real dashboard run at wandb.ai.

## Reproducing This Submission

1. `pip install -r requirements.txt`
2. Start the MLflow server: `mlflow server --host 127.0.0.1 --port 8080`
3. In a second terminal: `python kmeans_mlops_pipeline.py`
4. Open `http://127.0.0.1:8080` in a browser to see the logged run and
   registered model live.

## Notes

- MLflow 2.15.x is pinned deliberately in `requirements.txt` — a bleeding
  edge 3.x MLflow release was tested during development and had a UI bug
  that broke the experiment overview page; 2.15.x does not have this
  issue and its UI matches the assignment's reference screenshots.
- PCA reduces the TF-IDF program-name matrix to 75 components before
  clustering (within the 50-100 component range used for meaningful
  program-name groupings in Module 9).
