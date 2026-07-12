# Module 9 — Grad Cafe Program Clustering

## What this does

`kmeans.py` clusters similar Grad Cafe graduate program names together using
TF-IDF text vectorization, PCA dimensionality reduction, and K-Means
clustering (all via scikit-learn). It then uses the resulting clusters to
compare GRE and GRE Verbal score distributions between a Computer-Science-like
cluster and a Philosophy-like cluster, surfacing a data-quality issue in the
raw GRE scores along the way.

The pipeline:

1. **Load & clean** — loads the raw Grad Cafe JSON dataset, drops rows with a
   missing `program` value, and splits the combined `program` field
   (`"Program Name, University Name"`) on the first comma into separate
   `Program` and `University` columns.
2. **Vectorize** — converts the `Program` column into a TF-IDF sparse matrix.
3. **Initial clustering** — reduces the TF-IDF matrix to 2 dimensions with
   PCA and fits K-Means with 50 clusters (`max_iter=100`, `n_init=5`),
   producing a scatter plot and a sample of the clustered DataFrame.
4. **Elbow method** — reduces the TF-IDF matrix to a higher-dimensional PCA
   representation (75 components) and runs K-Means across k = 1–100 to plot
   inertia vs. cluster count, informing the choice of ~85 final clusters.
5. **Final clustering & analysis** — re-clusters at the selected cluster
   count, attaches labels back to the full cleaned dataset, and produces
   boxplots comparing GRE / GRE V scores for a Computer-Science-like cluster
   and a Philosophy-like cluster.

## How to run

```bash
pip install -r requirements.txt

python kmeans.py --input llm_extend_applicant_data.json --output-dir .
```

- `--input` — path to the raw Grad Cafe JSON dataset (default:
  `llm_extend_applicant_data.json` in the current directory)
- `--output-dir` — directory to write the output PNG files to (default:
  current directory)

The full run (including the k=1–100 elbow sweep) takes a few minutes on a
~30,000-row dataset. No internet access or AWS credentials are required —
this script runs entirely on a local JSON file.

## Dependencies

Python 3.10+ and the exact package versions pinned in `requirements.txt`
(validated against this script):

- pandas==3.0.2
- numpy==2.4.4
- scikit-learn==1.8.0
- matplotlib==3.10.8

## Expected outputs

| File | Description |
|---|---|
| `initial_cluster.png` | 2D PCA scatter plot colored by the initial 50-cluster K-Means assignment |
| `clustered_dataFrame.png` | 100-row rendered sample of Program / University / initial cluster |
| `elbow.png` | Inertia vs. cluster count (elbow method), used to select ~85 final clusters |
| `philosophy.png` | GRE / GRE V boxplot for the Philosophy-like cluster |
| `computer_science.png` | GRE / GRE V boxplot for the Computer-Science-like cluster |

## Notes

GRE and GRE V values are intentionally left unfiltered (not restricted to the
real score range) so that data-quality issues present in the raw data are
visible in the boxplots rather than being cleaned away — this is meant to
surface an issue that motivates further cleaning in a later step, not to
hide it. On this dataset, the resulting Computer Science boxplot reveals
that a meaningful share of "GRE" values (roughly 15% of valid entries) fall
within the GRE Verbal subscore range (130–170) rather than the real combined
GRE scale (260–340), suggesting GRE Verbal scores were mixed into the
combined GRE column for a subset of rows, in addition to a small number of
literal out-of-scale placeholder values.