"""Module 11 - MLOps tracking for the Module 9 Grad Cafe KMeans clustering
pipeline.

This script reuses the Module 9 data-loading, cleaning, TF-IDF
vectorization, and PCA workflow, then trains a single scikit-learn KMeans
model with the required tracking parameters and logs the run to MLflow
(and, optionally, to Weights & Biases) so training runs and their
performance can be tracked and compared over time.

Usage:
    # Start an MLflow tracking server first, in a separate terminal:
    #   mlflow server --host <your IP or 127.0.0.1> --port 8080

    python kmeans_mlops_pipeline.py --input llm_extend_applicant_data.json \\
        --tracking-uri http://127.0.0.1:8080

    # To additionally (or instead) log to Weights & Biases:
    python kmeans_mlops_pipeline.py --tracker both
    python kmeans_mlops_pipeline.py --tracker wandb
"""

import argparse
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
import wandb
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer

# Required clustering parameters for this assignment's tracked run.
CLUSTER_PARAMS = {
    "max_iter": 500,
    "n_clusters": 25,
    "n_init": 5,
    "random_state": 42,
}

# Number of PCA components the TF-IDF matrix is reduced to before
# clustering. 75 sits within the 50-100 component range used for the
# final Module 9 clustering, giving KMeans enough variability to resolve
# meaningful program-name groupings.
PCA_COMPONENTS = 75

MLFLOW_EXPERIMENT_NAME = "grad_cafe_kmeans_clustering"
MLFLOW_MODEL_NAME = "Clustering"
WANDB_PROJECT_NAME = "grad-cafe-kmeans-clustering"


def load_data(input_path: Path) -> pd.DataFrame:
    """Load the raw Grad Cafe JSON dataset into a DataFrame.

    Args:
        input_path: Path to the raw Grad Cafe JSON file.

    Returns:
        The raw dataset as a DataFrame.
    """
    return pd.read_json(input_path)


def clean_program_university(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows with a missing program and split the combined field.

    Rows where the "program" field is missing are dropped. The remaining
    "program" values (formatted as "Program Name, University Name") are
    split on the first comma into separate "Program" and "University"
    columns, with whitespace normalized on both.

    Args:
        df: Raw DataFrame containing a "program" column.

    Returns:
        A cleaned copy of the DataFrame with a "Program" column added.
    """
    cleaned = df[df["program"].notna()].copy()

    split_values = cleaned["program"].str.split(",", n=1, expand=True)
    cleaned["Program"] = split_values[0]

    cleaned["Program"] = (
        cleaned["Program"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    cleaned = cleaned[cleaned["Program"].notna() & (cleaned["Program"] != "")]
    return cleaned.reset_index(drop=True)


def vectorize_programs(programs: pd.Series) -> tuple:
    """Vectorize program names into a TF-IDF sparse matrix.

    Args:
        programs: Series of cleaned program name strings.

    Returns:
        A tuple of (fitted TfidfVectorizer, TF-IDF sparse matrix).
    """
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(programs)
    print(f"TF-IDF matrix shape: {tfidf_matrix.shape}, type: {type(tfidf_matrix)}")
    return vectorizer, tfidf_matrix


def reduce_dimensions(matrix, n_components: int) -> tuple:
    """Reduce a feature matrix to n_components with PCA.

    Args:
        matrix: Sparse or dense feature matrix.
        n_components: Number of principal components to keep.

    Returns:
        A tuple of (fitted PCA object, dense reduced feature array).
    """
    pca = PCA(n_components=n_components, random_state=CLUSTER_PARAMS["random_state"])
    reduced = pca.fit_transform(matrix.toarray())
    print(f"PCA output shape: {reduced.shape}")
    return pca, reduced


def train_kmeans(features, params: dict) -> KMeans:
    """Fit a KMeans model on the PCA-reduced features.

    Args:
        features: Dense feature array to cluster.
        params: Dictionary of KMeans constructor arguments.

    Returns:
        The fitted KMeans model.
    """
    model = KMeans(**params)
    model.fit(features)
    print(f"Trained KMeans: n_clusters={params['n_clusters']}, inertia_={model.inertia_:.4f}")
    return model


def log_to_mlflow(tracking_uri: str, model: KMeans, params: dict, features) -> None:
    """Log the clustering run's parameters, metric, and model to MLflow.

    Args:
        tracking_uri: URI of the running MLflow tracking server.
        model: The fitted KMeans model.
        params: The clustering parameters used to train the model.
        features: The PCA-reduced feature array the model was trained on,
            used to provide a model signature via a small input example.
    """
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(run_name="kmeans-clustering-run"):
        mlflow.log_params(params)
        mlflow.log_metric("inertia", model.inertia_)
        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            registered_model_name=MLFLOW_MODEL_NAME,
            input_example=features[:5],
        )
    print(f"Logged run to MLflow at {tracking_uri} (experiment: {MLFLOW_EXPERIMENT_NAME})")


def log_to_wandb(model: KMeans, params: dict, output_dir: Path, mode: str) -> None:
    """Log the clustering run's parameters, metric, and model to wandb.

    Args:
        model: The fitted KMeans model.
        params: The clustering parameters used to train the model.
        output_dir: Directory to temporarily save the model artifact to
            before it is uploaded to wandb.
        mode: wandb run mode ("online", "offline", or "disabled").
    """
    run = wandb.init(project=WANDB_PROJECT_NAME, config=params, mode=mode)
    wandb.log({"inertia": model.inertia_})

    model_path = output_dir / "kmeans_model.joblib"
    joblib.dump(model, model_path)

    artifact = wandb.Artifact(name="kmeans-clustering-model", type="model")
    artifact.add_file(str(model_path))
    run.log_artifact(artifact)

    wandb.finish()
    print(f"Logged run to wandb (project: {WANDB_PROJECT_NAME}, mode: {mode})")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        The parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Track a KMeans clustering run with MLflow and/or wandb."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("llm_extend_applicant_data.json"),
        help="Path to the raw Grad Cafe JSON dataset.",
    )
    parser.add_argument(
        "--tracking-uri",
        type=str,
        default="http://127.0.0.1:8080",
        help="MLflow tracking server URI.",
    )
    parser.add_argument(
        "--tracker",
        choices=["mlflow", "wandb", "both"],
        default="mlflow",
        help="Which tracking backend(s) to log this run to.",
    )
    parser.add_argument(
        "--wandb-mode",
        choices=["online", "offline", "disabled"],
        default="online",
        help="wandb run mode. Use 'online' with an authenticated account.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to save intermediate model artifacts to.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the full Module 11 clustering and tracking pipeline."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    raw_df = load_data(args.input)
    df = clean_program_university(raw_df)
    print(f"Number of Entries: {len(df):,}")
    print(f"Number of Program Input Names: {df['Program'].nunique():,}")

    _, tfidf_matrix = vectorize_programs(df["Program"])
    _, pca_features = reduce_dimensions(tfidf_matrix, n_components=PCA_COMPONENTS)
    model = train_kmeans(pca_features, CLUSTER_PARAMS)

    if args.tracker in ("mlflow", "both"):
        log_to_mlflow(args.tracking_uri, model, CLUSTER_PARAMS, pca_features)

    if args.tracker in ("wandb", "both"):
        log_to_wandb(model, CLUSTER_PARAMS, args.output_dir, args.wandb_mode)


if __name__ == "__main__":
    main()
