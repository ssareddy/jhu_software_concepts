"""Module 9 - K-Means clustering of Grad Cafe program names.

This script loads the raw Grad Cafe dataset, cleans the combined
program/university field, vectorizes program names with TF-IDF, reduces
dimensionality with PCA, and clusters similar program names together using
K-Means. It then uses the resulting clusters to compare GRE and GRE Verbal
score distributions between a Computer-Science-like cluster and a
Philosophy-like cluster.

Usage:
    python kmeans.py --input llm_extend_applicant_data.json --output-dir .

Outputs (written to --output-dir):
    initial_cluster.png     - 2D PCA scatter plot, colored by initial
                               50-cluster K-Means assignment
    clustered_dataFrame.png - 100-row sample of Program/University/Cluster
    elbow.png                - inertia vs. cluster count (elbow method)
    philosophy.png           - GRE / GRE V boxplot for the Philosophy-like
                               cluster
    computer_science.png     - GRE / GRE V boxplot for the Computer-Science-
                               like cluster
"""

import argparse
import re
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer

RANDOM_STATE = 42
INITIAL_N_CLUSTERS = 50
INITIAL_MAX_ITER = 100
INITIAL_N_INIT = 5
ELBOW_PCA_COMPONENTS = 75
ELBOW_MAX_K = 100
FINAL_N_CLUSTERS = 85


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
        A cleaned copy of the DataFrame with "Program" and "University"
        columns added.
    """
    cleaned = df[df["program"].notna()].copy()

    split_values = cleaned["program"].str.split(",", n=1, expand=True)
    cleaned["Program"] = split_values[0]
    cleaned["University"] = split_values[1] if split_values.shape[1] > 1 else None

    for col in ("Program", "University"):
        cleaned[col] = (
            cleaned[col]
            .astype(str)
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )

    cleaned = cleaned[cleaned["Program"].notna() & (cleaned["Program"] != "")]
    return cleaned.reset_index(drop=True)


def report_dataset_stats(df: pd.DataFrame) -> None:
    """Print the number of entries and unique program names.

    Args:
        df: Cleaned DataFrame containing a "Program" column.
    """
    print(f"Number of Entries: {len(df):,}")
    print(f"Number of Program Input Names: {df['Program'].nunique():,}")


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
    pca = PCA(n_components=n_components, random_state=RANDOM_STATE)
    reduced = pca.fit_transform(matrix.toarray())
    print(f"PCA output shape: {reduced.shape}")
    print(pca)
    return pca, reduced


def run_kmeans(
    features: np.ndarray,
    n_clusters: int,
    max_iter: int = INITIAL_MAX_ITER,
    n_init: int = INITIAL_N_INIT,
) -> tuple:
    """Fit K-Means on a feature array.

    Args:
        features: Dense feature array to cluster.
        n_clusters: Number of clusters to fit.
        max_iter: Maximum number of K-Means iterations.
        n_init: Number of K-Means initializations to try.

    Returns:
        A tuple of (fitted KMeans object, cluster label array).
    """
    kmeans = KMeans(
        n_clusters=n_clusters,
        max_iter=max_iter,
        n_init=n_init,
        random_state=RANDOM_STATE,
    )
    labels = kmeans.fit_predict(features)
    return kmeans, labels


def plot_initial_clusters(
    pca_features: np.ndarray, labels: np.ndarray, output_path: Path
) -> None:
    """Plot a 2D PCA scatter plot colored by cluster label.

    Args:
        pca_features: 2-column PCA-reduced feature array.
        labels: Cluster label for each row.
        output_path: File path to save the resulting PNG to.
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(
        pca_features[:, 0],
        pca_features[:, 1],
        c=labels,
        cmap="tab20",
        s=15,
        alpha=0.7,
    )
    ax.set_title("K-Means Clustering of Grad Cafe Program Names (k=50)")
    ax.set_xlabel("PCA Component 1")
    ax.set_ylabel("PCA Component 2")
    legend_handles, _ = scatter.legend_elements(num=10)
    ax.legend(
        legend_handles,
        [f"Cluster {i}" for i in range(len(legend_handles))],
        title="Cluster (sample)",
        loc="upper right",
        fontsize="x-small",
        ncol=2,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def save_dataframe_image(
    df: pd.DataFrame, n_rows: int, output_path: Path
) -> None:
    """Render a sample of a DataFrame to a PNG image.

    Args:
        df: DataFrame to sample and render.
        n_rows: Number of rows to include in the rendered sample.
        output_path: File path to save the resulting PNG to.
    """
    sample = df.head(n_rows)
    row_height = 0.22
    fig, ax = plt.subplots(figsize=(10, max(4, row_height * (n_rows + 1))))
    ax.axis("off")
    table = ax.table(
        cellText=sample.values,
        colLabels=sample.columns,
        loc="center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1, 1.1)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def compute_elbow_inertias(features: np.ndarray, max_k: int) -> list:
    """Compute K-Means inertia across a range of cluster counts.

    Args:
        features: Dense feature array to cluster.
        max_k: Maximum number of clusters to try (inclusive).

    Returns:
        A list of inertia values for k = 1 .. max_k.
    """
    inertias = []
    for k in range(1, max_k + 1):
        kmeans, _ = run_kmeans(features, n_clusters=k)
        inertias.append(kmeans.inertia_)
    return inertias


def plot_elbow(inertias: list, output_path: Path) -> None:
    """Plot the elbow-method curve of inertia vs. cluster count.

    Args:
        inertias: List of inertia values, one per cluster count starting
            at k=1.
        output_path: File path to save the resulting PNG to.
    """
    k_values = range(1, len(inertias) + 1)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(k_values, inertias, marker="o", markersize=3, label="Inertia")
    ax.set_title("The Elbow Method using Inertia")
    ax.set_xlabel("Number of Clusters (k)")
    ax.set_ylabel("Inertia")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")
    # An approximate elbow of ~85 clusters was selected for this dataset:
    # inertia continues to decline gradually with no single sharp "elbow",
    # so 85 was chosen as a reasonable point of diminishing returns while
    # still resolving distinct program-name groupings (e.g. separating
    # "Information Studies" from "Information").


def find_cluster_by_keyword(
    df: pd.DataFrame, keyword: str, cluster_col: str
) -> Optional[int]:
    """Find the cluster ID most associated with a given keyword.

    Searches the "Program" column for the keyword (case-insensitive) and
    returns the most common cluster label among matching rows.

    Args:
        df: DataFrame containing "Program" and cluster_col columns.
        keyword: Keyword to search for within program names.
        cluster_col: Name of the column containing cluster labels.

    Returns:
        The most common cluster ID among matching rows, or None if no
        rows matched the keyword.
    """
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    matches = df[df["Program"].str.contains(pattern, na=False)]
    if matches.empty:
        return None
    return int(matches[cluster_col].mode().iloc[0])


def report_gre_summary(df: pd.DataFrame, cluster_label: str) -> tuple:
    """Compute and print GRE / GRE V summary statistics for a cluster.

    Args:
        df: DataFrame subset belonging to a single cluster, containing
            "GRE" and "GRE V" columns.
        cluster_label: Human-readable name for the cluster (used in the
            printed report).

    Returns:
        A tuple of (GRE Series, GRE V Series) with missing values dropped,
        for reuse by the boxplot step.
    """
    gre = pd.to_numeric(df["GRE"], errors="coerce").dropna()
    gre_v = pd.to_numeric(df["GRE V"], errors="coerce").dropna()

    print(f"\n=== GRE / GRE V Summary - {cluster_label} Cluster ===")
    for name, series in (("GRE", gre), ("GRE V", gre_v)):
        if len(series) > 0:
            print(
                f"{name}: n={len(series)}, min={series.min():.1f}, "
                f"max={series.max():.1f}, mean={series.mean():.2f}, "
                f"median={series.median():.1f}"
            )
        else:
            print(f"{name}: no valid values in this cluster")

    return gre, gre_v


def plot_gre_boxplot(
    gre: pd.Series, gre_v: pd.Series, cluster_label: str, output_path: Path
) -> None:
    """Plot GRE and GRE V distributions for a cluster as a boxplot.

    Args:
        gre: Cleaned GRE score values for the cluster.
        gre_v: Cleaned GRE V score values for the cluster.
        cluster_label: Human-readable name for the cluster (used in the
            plot title).
        output_path: File path to save the resulting PNG to.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    box_data = [gre, gre_v]
    box_labels = [f"GRE (n={len(gre)})", f"GRE V (n={len(gre_v)})"]
    bp = ax.boxplot(box_data, tick_labels=box_labels, patch_artist=True)
    for patch, color in zip(bp["boxes"], ["lightsteelblue", "lightsalmon"]):
        patch.set_facecolor(color)

    ax.set_title(f"GRE Score Distribution - {cluster_label} Cluster")
    ax.set_ylabel("Score (points)")
    ax.set_xlabel("GRE Section")
    ax.legend(
        [bp["boxes"][0], bp["boxes"][1]],
        ["GRE (Combined)", "GRE V (Verbal)"],
        loc="upper right",
    )
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        The parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Cluster Grad Cafe program names with TF-IDF + K-Means."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("llm_extend_applicant_data.json"),
        help="Path to the raw Grad Cafe JSON dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to write output PNG files to.",
    )
    return parser.parse_args()


def run_initial_clustering(input_path: Path, output_dir: Path) -> tuple:
    """Run Section 1: load, clean, vectorize, and produce initial clusters.

    Args:
        input_path: Path to the raw Grad Cafe JSON dataset.
        output_dir: Directory to write output PNG files to.

    Returns:
        A tuple of (cleaned DataFrame with an "initial_cluster" column,
        fitted TF-IDF sparse matrix).
    """
    raw_df = load_data(input_path)
    df = clean_program_university(raw_df)
    report_dataset_stats(df)

    _, tfidf_matrix = vectorize_programs(df["Program"])
    _, pca_2d = reduce_dimensions(tfidf_matrix, n_components=2)
    _, initial_labels = run_kmeans(pca_2d, n_clusters=INITIAL_N_CLUSTERS)
    df["initial_cluster"] = initial_labels

    plot_initial_clusters(
        pca_2d, initial_labels, output_dir / "initial_cluster.png"
    )
    save_dataframe_image(
        df[["Program", "University", "initial_cluster"]],
        n_rows=100,
        output_path=output_dir / "clustered_dataFrame.png",
    )
    return df, tfidf_matrix


def run_elbow_analysis(tfidf_matrix, output_dir: Path) -> np.ndarray:
    """Run Section 2: expand PCA and produce the elbow-method plot.

    Args:
        tfidf_matrix: Fitted TF-IDF sparse matrix from Section 1.
        output_dir: Directory to write output PNG files to.

    Returns:
        The higher-dimensional PCA-reduced feature array used for the
        elbow sweep, reused for final clustering in Section 3.
    """
    _, pca_wide = reduce_dimensions(
        tfidf_matrix, n_components=ELBOW_PCA_COMPONENTS
    )
    inertias = compute_elbow_inertias(pca_wide, max_k=ELBOW_MAX_K)
    plot_elbow(inertias, output_dir / "elbow.png")
    return pca_wide


def run_final_analysis(
    df: pd.DataFrame, pca_wide: np.ndarray, output_dir: Path
) -> None:
    """Run Section 3: final clustering and GRE/GRE V cluster analysis.

    Args:
        df: Cleaned DataFrame from Section 1.
        pca_wide: Higher-dimensional PCA features from Section 2.
        output_dir: Directory to write output PNG files to.
    """
    _, final_labels = run_kmeans(pca_wide, n_clusters=FINAL_N_CLUSTERS)
    df["cluster"] = final_labels

    cs_cluster = find_cluster_by_keyword(df, "Computer Science", "cluster")
    philosophy_cluster = find_cluster_by_keyword(df, "Philosophy", "cluster")

    if cs_cluster is not None:
        cs_gre, cs_gre_v = report_gre_summary(
            df[df["cluster"] == cs_cluster], "Computer Science"
        )
        plot_gre_boxplot(
            cs_gre,
            cs_gre_v,
            "Computer Science",
            output_dir / "computer_science.png",
        )
    else:
        print("No Computer Science-like cluster found.")

    if philosophy_cluster is not None:
        phil_gre, phil_gre_v = report_gre_summary(
            df[df["cluster"] == philosophy_cluster], "Philosophy"
        )
        plot_gre_boxplot(
            phil_gre, phil_gre_v, "Philosophy", output_dir / "philosophy.png"
        )
    else:
        print("No Philosophy-like cluster found.")

    # Conclusion: The Computer Science cluster's GRE boxplot shows a wide,
    # bimodal spread that dips well below the real GRE combined-score floor
    # of 260 (its 25th percentile lands around 168 -- squarely within the
    # GRE Verbal subscore range of 130-170, not the combined scale). This
    # suggests GRE Verbal scores were mixed into the combined "GRE" column
    # for a meaningful share of rows, in addition to a small number of
    # literal out-of-scale placeholder values (e.g. 999). Both are signs
    # that further data cleaning is needed before GRE can be trusted for
    # legitimate score analysis.


def main() -> None:
    """Run the full Module 9 clustering pipeline."""
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    df, tfidf_matrix = run_initial_clustering(args.input, output_dir)
    pca_wide = run_elbow_analysis(tfidf_matrix, output_dir)
    run_final_analysis(df, pca_wide, output_dir)


if __name__ == "__main__":
    main()
