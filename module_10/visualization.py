"""Module 10 - Exploratory data analysis and visualizations for the
research question: "Can the price of a diamond be determined based upon
its features?"

This script loads the Kaggle Diamonds dataset, cleans out physically
impossible rows, performs exploratory analysis on how carat weight and
the categorical "4 Cs" (cut, color, clarity) relate to price, and produces
four visualizations: three with Seaborn (saved as PNGs) and one interactive,
animated visualization with Plotly (saved as HTML).

Usage:
    python visualization.py --input diamonds.csv --output-dir .

Outputs (written to --output-dir):
    carat_vs_price.png       - Seaborn scatter plot of carat vs. price,
                                colored by cut
    price_by_clarity.png     - Seaborn boxplot of price distribution by
                                clarity grade (ordered worst to best)
    correlation_heatmap.png  - Seaborn heatmap of numeric feature
                                correlations
    price_explorer.html      - Interactive, animated Plotly scatter of
                                carat vs. price, animated across cut grade
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns

# A single, consistent, colorblind-friendly palette used across every
# categorical encoding in this file (Seaborn and Plotly alike), per the
# "use a consistent color palette" and "avoid unusual coloring" guidance.
PALETTE = sns.color_palette("viridis", 8).as_hex()

# The "4 Cs" categorical grades are ordinal, not alphabetical. Plotting
# them in their true quality order (rather than default alphabetical
# sorting) is required to "accurately and clearly represent the
# underlying data" and to "use the right type of chart for the job."
CUT_ORDER = ["Fair", "Good", "Very Good", "Premium", "Ideal"]
COLOR_ORDER = ["J", "I", "H", "G", "F", "E", "D"]  # worst -> best
CLARITY_ORDER = ["I1", "SI2", "SI1", "VS2", "VS1", "VVS2", "VVS1", "IF"]

# Diamonds in this dataset physically range up to roughly 10-11mm per
# side. Any x/y/z value of 0 or far outside that range is a data entry
# error (e.g. a misplaced decimal), not a real diamond, and is excluded
# during cleaning.
MAX_PLAUSIBLE_DIMENSION_MM = 15.0


def load_data(input_path: Path) -> pd.DataFrame:
    """Load the raw diamonds dataset into a DataFrame.

    Args:
        input_path: Path to the diamonds CSV file.

    Returns:
        The raw dataset as a DataFrame.
    """
    return pd.read_csv(input_path)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the unused index column and physically impossible rows.

    Diamonds with a length, width, or depth of 0mm, or with a dimension
    far outside the dataset's realistic range, are data entry errors
    (e.g. a misplaced decimal point) rather than genuine measurements,
    and are excluded rather than guessed at.

    Args:
        df: Raw diamonds DataFrame.

    Returns:
        A cleaned copy of the DataFrame.
    """
    cleaned = df.drop(columns=["Unnamed: 0"], errors="ignore").copy()

    zero_dim_mask = (cleaned["x"] == 0) | (cleaned["y"] == 0) | (cleaned["z"] == 0)
    outlier_mask = (
        (cleaned["x"] > MAX_PLAUSIBLE_DIMENSION_MM)
        | (cleaned["y"] > MAX_PLAUSIBLE_DIMENSION_MM)
        | (cleaned["z"] > MAX_PLAUSIBLE_DIMENSION_MM)
    )
    invalid_mask = zero_dim_mask | outlier_mask

    print(f"Raw rows: {len(cleaned):,}")
    print(f"Rows with a zero x/y/z dimension: {int(zero_dim_mask.sum())}")
    print(
        f"Rows with an implausible x/y/z dimension "
        f"(> {MAX_PLAUSIBLE_DIMENSION_MM}mm): {int(outlier_mask.sum())}"
    )
    print(f"Total invalid rows removed: {int(invalid_mask.sum())}")

    cleaned = cleaned[~invalid_mask].reset_index(drop=True)
    print(f"Cleaned rows: {len(cleaned):,}")
    return cleaned


def explore_data(df: pd.DataFrame) -> None:
    """Run and print exploratory sub-question analysis on the cleaned data.

    Args:
        df: Cleaned diamonds DataFrame.
    """
    print("\n=== Numeric Feature Summary ===")
    print(df[["carat", "depth", "table", "price", "x", "y", "z"]].describe())

    carat_price_corr = df["carat"].corr(df["price"])
    print(f"\nCorrelation between carat and price: {carat_price_corr:.4f}")

    print("\n=== Mean Price by Cut ===")
    print(
        df.groupby("cut", observed=True)["price"]
        .mean()
        .reindex(CUT_ORDER)
        .round(2)
    )

    print("\n=== Mean Price by Color (worst to best: J -> D) ===")
    print(
        df.groupby("color", observed=True)["price"]
        .mean()
        .reindex(COLOR_ORDER)
        .round(2)
    )

    print("\n=== Mean Price by Clarity (worst to best: I1 -> IF) ===")
    print(
        df.groupby("clarity", observed=True)["price"]
        .mean()
        .reindex(CLARITY_ORDER)
        .round(2)
    )

    # Price alone conflates size (carat) with quality grade. Normalizing
    # by carat isolates whether quality grade affects price independent
    # of size, a sub-question that directly supports the main research
    # question of whether price can be explained by features beyond size.
    df["price_per_carat"] = df["price"] / df["carat"]
    print("\n=== Mean Price-per-Carat by Clarity (size-normalized) ===")
    print(
        df.groupby("clarity", observed=True)["price_per_carat"]
        .mean()
        .reindex(CLARITY_ORDER)
        .round(2)
    )


def plot_carat_vs_price_scatter(df: pd.DataFrame, output_path: Path) -> None:
    """Plot a Seaborn scatter plot of carat vs. price, colored by cut.

    Args:
        df: Cleaned diamonds DataFrame.
        output_path: File path to save the resulting PNG to.
    """
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.scatterplot(
        data=df,
        x="carat",
        y="price",
        hue="cut",
        hue_order=CUT_ORDER,
        palette=PALETTE[: len(CUT_ORDER)],
        alpha=0.35,
        s=15,
        edgecolor="none",
        ax=ax,
    )
    ax.set_title("Diamond Price vs. Carat Weight, by Cut Grade")
    ax.set_xlabel("Carat Weight (ct)")
    ax.set_ylabel("Price (USD)")
    ax.legend(title="Cut", loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_price_by_clarity_box(df: pd.DataFrame, output_path: Path) -> None:
    """Plot a Seaborn boxplot of price distribution by clarity grade.

    Args:
        df: Cleaned diamonds DataFrame.
        output_path: File path to save the resulting PNG to.
    """
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.boxplot(
        data=df,
        x="clarity",
        y="price",
        order=CLARITY_ORDER,
        hue="clarity",
        hue_order=CLARITY_ORDER,
        palette=PALETTE[: len(CLARITY_ORDER)],
        legend=False,
        ax=ax,
    )
    ax.set_title("Diamond Price Distribution by Clarity Grade")
    ax.set_xlabel("Clarity Grade (worst to best: I1 -> IF)")
    ax.set_ylabel("Price (USD)")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_correlation_heatmap(df: pd.DataFrame, output_path: Path) -> None:
    """Plot a Seaborn heatmap of correlations among numeric features.

    Args:
        df: Cleaned diamonds DataFrame.
        output_path: File path to save the resulting PNG to.
    """
    numeric_cols = ["carat", "depth", "table", "price", "x", "y", "z"]
    corr = df[numeric_cols].corr()

    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap="viridis",
        vmin=-1,
        vmax=1,
        square=True,
        linewidths=0.5,
        cbar_kws={"label": "Correlation Coefficient"},
        ax=ax,
    )
    ax.set_title("Correlation Between Diamond Numeric Features")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def build_animated_price_scatter_figure(df: pd.DataFrame):
    """Build the interactive, animated Plotly scatter figure object.

    The animation steps through cut grade (Fair -> Ideal), letting a
    viewer watch how the carat/price relationship shifts as cut quality
    improves, with point color encoding color grade and point size
    encoding table percentage. This is deliberately not a re-skin of the
    static Seaborn scatter: it adds two more encoded variables (color
    grade, table %) and an animated dimension (cut) that a static PNG
    cannot show.

    Args:
        df: Cleaned diamonds DataFrame.

    Returns:
        A Plotly Figure object, reusable both for saving to HTML and for
        embedding natively in the Dash dashboard.
    """
    plot_df = df.copy()
    plot_df["cut"] = pd.Categorical(plot_df["cut"], categories=CUT_ORDER, ordered=True)
    plot_df["color"] = pd.Categorical(
        plot_df["color"], categories=COLOR_ORDER, ordered=True
    )
    plot_df = plot_df.sort_values("cut")

    fig = px.scatter(
        plot_df,
        x="carat",
        y="price",
        animation_frame="cut",
        color="color",
        category_orders={"cut": CUT_ORDER, "color": COLOR_ORDER},
        color_discrete_sequence=PALETTE[: len(COLOR_ORDER)],
        size="table",
        size_max=12,
        opacity=0.6,
        hover_data=["clarity", "depth"],
        labels={
            "carat": "Carat Weight (ct)",
            "price": "Price (USD)",
            "color": "Color Grade",
            "table": "Table (%)",
        },
        title="Diamond Price vs. Carat Weight, Animated by Cut Grade",
        range_x=[0, plot_df["carat"].max() * 1.05],
        range_y=[0, plot_df["price"].max() * 1.05],
    )
    fig.update_layout(
        legend_title_text="Color Grade",
        xaxis_title="Carat Weight (ct)",
        yaxis_title="Price (USD)",
    )
    return fig


def plot_animated_price_scatter(df: pd.DataFrame, output_path: Path) -> None:
    """Build and save the animated Plotly scatter figure as HTML.

    Args:
        df: Cleaned diamonds DataFrame.
        output_path: File path to save the resulting HTML to.
    """
    fig = build_animated_price_scatter_figure(df)
    fig.write_html(
        output_path, auto_play=False, config={"displayModeBar": False}
    )
    print(f"Saved: {output_path}")


def add_input_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared --input CLI argument to a parser.

    Shared by visualization.py and dashboard.py so both scripts accept
    the same dataset path option without duplicating the argument
    definition.

    Args:
        parser: The ArgumentParser to add the argument to.
    """
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("diamonds.csv"),
        help="Path to the diamonds CSV dataset.",
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        The parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Explore and visualize the diamonds pricing dataset."
    )
    add_input_argument(parser)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to write output visualization files to.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the full Module 10 exploratory analysis and visualization suite."""
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_df = load_data(args.input)
    df = clean_data(raw_df)
    explore_data(df)

    plot_carat_vs_price_scatter(df, output_dir / "carat_vs_price.png")
    plot_price_by_clarity_box(df, output_dir / "price_by_clarity.png")
    plot_correlation_heatmap(df, output_dir / "correlation_heatmap.png")
    plot_animated_price_scatter(df, output_dir / "price_explorer.html")


if __name__ == "__main__":
    main()
