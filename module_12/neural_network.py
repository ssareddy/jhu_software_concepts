"""Module 12 - Two-Layer Neural Network for Graduate Admissions Prediction.

Implements a binary classifier, built from scratch using only NumPy, that
predicts whether a graduate school applicant was Accepted or Rejected based
on six features: GPA, GRE, GRE Verbal, GRE Analytical Writing, degree type
(Master's vs. PhD), and citizenship (International vs. Local/American).

scikit-learn is used only for the train/test split, per the assignment's
requirements. The network itself -- forward propagation, backpropagation,
and gradient descent -- is implemented entirely in NumPy.

Usage:
    python neural_network.py --input applicant_data.jsonl --output-dir .
"""

import argparse
import json
from pathlib import Path
from typing import NamedTuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# --- Required hyperparameters (exact values per assignment spec) ---
RANDOM_SEED = 42
HIDDEN_UNITS = 6
LEARNING_RATE = 0.05
MAX_EPOCHS = 10000
PATIENCE = 100

FEATURE_COLUMNS = [
    "gpa",
    "gre",
    "gre_v",
    "gre_aw",
    "ms_vs_phd",
    "international_vs_local",
]


def load_and_prepare_data(input_path: Path) -> pd.DataFrame:
    """Load the JSON-Lines applicant dataset and engineer model features.

    Loads the raw records, keeps only rows with a usable applicant_status
    (Accepted/Rejected) and masters_or_phd (Masters/PhD) value, converts
    the string-valued numeric columns to floats, and builds the binary
    feature columns and target variable the model will use.

    Args:
        input_path: Path to the JSON-Lines applicant dataset.

    Returns:
        The cleaned DataFrame, including the six model input features and
        the target column.
    """
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    df = pd.DataFrame(records)
    original_row_count = len(df)

    # Keep only rows with a usable applicant_status and degree type.
    df = df[df["applicant_status"].isin(["Accepted", "Rejected"])].copy()
    df = df[df["masters_or_phd"].isin(["Masters", "PhD"])].copy()
    filtered_row_count = len(df)

    # Convert string-valued numeric columns to floats. Values that can't be
    # parsed (or were already missing) become NaN, which the preprocessing
    # step in split_and_preprocess() fills in using training-set medians.
    for col in ("gpa", "gre", "gre_v", "gre_aw"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Binary feature columns.
    df["ms_vs_phd"] = (df["masters_or_phd"] == "PhD").astype(float)
    df["international_vs_local"] = (df["citizenship"] == "International").astype(float)

    # Target variable.
    df["target"] = (df["applicant_status"] == "Accepted").astype(float)

    accepted_count = int((df["target"] == 1).sum())
    rejected_count = int((df["target"] == 0).sum())

    print("=== Section 1: Load and Prepare the Applicant Dataset ===")
    print(f"Number of rows in original dataset: {original_row_count}")
    print(f"Number of rows remaining after filtering: {filtered_row_count}")
    print(f"Number of Accepted rows: {accepted_count}")
    print(f"Number of Rejected rows: {rejected_count}")
    print(f"Final input features: {FEATURE_COLUMNS}")
    print()
    print("First few rows of the cleaned DataFrame:")
    print(df[FEATURE_COLUMNS + ["target"]].head())
    print()

    return df


def print_split_summary(
    x_train: np.ndarray,
    x_test: np.ndarray,
    train_medians: np.ndarray,
    train_means: np.ndarray,
    train_stds: np.ndarray,
) -> None:
    """Print the required Section 2 output: sizes and training statistics.

    Args:
        x_train: Training feature array (used only for its size here).
        x_test: Test feature array (used only for its size here).
        train_medians: Training-set feature medians.
        train_means: Training-set feature means.
        train_stds: Training-set feature standard deviations.
    """
    print("=== Section 2: Split and Preprocess the Data ===")
    print(f"Training set size: {x_train.shape[0]}")
    print(f"Test set size: {x_test.shape[0]}")
    print()
    print("Training-set medians:")
    for name, val in zip(FEATURE_COLUMNS, train_medians):
        print(f"  {name}: {val:.4f}")
    print("Training-set means:")
    for name, val in zip(FEATURE_COLUMNS, train_means):
        print(f"  {name}: {val:.4f}")
    print("Training-set standard deviations:")
    for name, val in zip(FEATURE_COLUMNS, train_stds):
        print(f"  {name}: {val:.4f}")
    print()
    print(
        "Medians, means, and standard deviations are computed from the "
        "training set only -- never the full dataset -- to keep the test "
        "set a genuinely unseen holdout. If test-set values were used to "
        "compute these statistics, information about the test set would "
        "leak into preprocessing before the model is ever evaluated on it, "
        "making test performance look better than the model would actually "
        "achieve on truly new, unseen applicants."
    )
    print()


def split_and_preprocess(df: pd.DataFrame) -> tuple:
    """Split the data and apply leakage-safe preprocessing.

    Splits into 80% train / 20% test using scikit-learn's train_test_split
    (the only scikit-learn usage in this file). Missing values are filled
    using training-set medians, and features are standardized using
    training-set means and standard deviations -- both computed from the
    training set only, then applied unchanged to the test set, so that no
    information from the test set leaks into preprocessing.

    Args:
        df: Cleaned DataFrame from load_and_prepare_data(), containing the
            six feature columns and the target column.

    Returns:
        A tuple of (x_train, x_test, y_train, y_test, train_medians,
        train_means, train_stds).
    """
    features = df[FEATURE_COLUMNS].to_numpy(dtype=float)
    targets = df["target"].to_numpy(dtype=float).reshape(-1, 1)

    x_train, x_test, y_train, y_test = train_test_split(
        features, targets, test_size=0.2, random_state=RANDOM_SEED, shuffle=True
    )

    # Medians computed from the training set only, then used to fill
    # missing values in both the training and test sets.
    train_medians = np.nanmedian(x_train, axis=0)
    x_train = np.where(np.isnan(x_train), train_medians, x_train)
    x_test = np.where(np.isnan(x_test), train_medians, x_test)

    # Means and standard deviations computed from the (now-filled) training
    # set only, then used to standardize both training and test sets.
    train_means = x_train.mean(axis=0)
    train_stds = x_train.std(axis=0)
    train_stds = np.where(train_stds == 0, 1.0, train_stds)

    x_train_scaled = (x_train - train_means) / train_stds
    x_test_scaled = (x_test - train_means) / train_stds

    print_split_summary(x_train, x_test, train_medians, train_means, train_stds)

    return x_train_scaled, x_test_scaled, y_train, y_test, train_medians, train_means, train_stds


class TwoLayerNeuralNetwork:
    """A fully-connected two-layer neural network, implemented from scratch.

    Architecture:
        Input layer:  6 features
        Hidden layer: 6 units, sigmoid activation
        Output layer: 1 unit, sigmoid activation

    Parameter shapes (n_features=6, n_hidden=6):
        W1: (6, 6) -- input-to-hidden weights. Each of the 6 hidden units
            has its own weight for each of the 6 input features.
        b1: (1, 6) -- one bias per hidden unit.
        W2: (6, 1) -- hidden-to-output weights. The single output unit has
            one weight per hidden unit.
        b2: (1, 1) -- one bias for the output unit.

    What the hidden layer computes: for each of its 6 units, a weighted sum
    of the 6 standardized input features plus a bias, passed through the
    sigmoid function -- producing 6 activations, each squashed to (0, 1).

    What the output layer computes: a weighted sum of the 6 hidden-layer
    activations plus a bias, passed through sigmoid again -- producing a
    single value in (0, 1).

    Why the output can be read as a probability-like score: sigmoid always
    maps its input to the open interval (0, 1), and the network is trained
    (via MSE against 0/1 targets) to push that value toward 1 for Accepted
    applicants and toward 0 for Rejected applicants. A value near 1 means
    the network leans toward predicting "Accepted"; a value near 0 means it
    leans toward "Rejected" -- the same shape as a predicted probability,
    even though the network was never explicitly trained with a
    probabilistic loss function.
    """

    def __init__(self, n_features: int, n_hidden: int, random_seed: int = RANDOM_SEED):
        """Initialize weights from N(0, 0.1) and biases to 0.

        Args:
            n_features: Number of input features.
            n_hidden: Number of hidden units.
            random_seed: Seed for reproducible weight initialization.
        """
        rng = np.random.default_rng(random_seed)
        self.w1 = rng.normal(loc=0.0, scale=0.1, size=(n_features, n_hidden))
        self.b1 = np.zeros((1, n_hidden))
        self.w2 = rng.normal(loc=0.0, scale=0.1, size=(n_hidden, 1))
        self.b2 = np.zeros((1, 1))
        # Cached activations from the most recent forward() call, reused by
        # backward() so the forward pass never has to be repeated.
        self.hidden_activation = None
        self.output_activation = None

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        """Apply the sigmoid activation function element-wise."""
        return 1.0 / (1.0 + np.exp(-z))

    def forward(self, features: np.ndarray) -> np.ndarray:
        """Run a forward pass through the network.

        Args:
            features: Input feature array of shape (n_samples, 6).

        Returns:
            Output activations of shape (n_samples, 1), each in (0, 1).
        """
        hidden_input = features @ self.w1 + self.b1
        self.hidden_activation = self._sigmoid(hidden_input)

        output_input = self.hidden_activation @ self.w2 + self.b2
        self.output_activation = self._sigmoid(output_input)

        return self.output_activation

    def _output_layer_delta(self, targets: np.ndarray) -> np.ndarray:
        """Compute the backprop delta term at the output layer.

        For MSE loss L = mean((output - target)^2), dL/d(output) is
        2 * (output - target) / n_samples. Combined with the sigmoid
        derivative output * (1 - output) via the chain rule, this gives
        the delta term used to compute the output layer's gradients.

        Args:
            targets: True target values, shape (n_samples, 1).

        Returns:
            The output-layer delta term, shape (n_samples, 1).
        """
        n_samples = targets.shape[0]
        d_loss_d_output = 2 * (self.output_activation - targets) / n_samples
        d_output_d_z2 = self.output_activation * (1 - self.output_activation)
        return d_loss_d_output * d_output_d_z2

    def _hidden_layer_delta(self, delta_output: np.ndarray) -> np.ndarray:
        """Compute the backprop delta term at the hidden layer.

        Backpropagates the output layer's delta through W2, then applies
        the hidden layer's own sigmoid derivative via the chain rule.

        Args:
            delta_output: The output-layer delta term from
                _output_layer_delta(), shape (n_samples, 1).

        Returns:
            The hidden-layer delta term, shape (n_samples, n_hidden).
        """
        d_hidden = delta_output @ self.w2.T
        d_hidden_d_z1 = self.hidden_activation * (1 - self.hidden_activation)
        return d_hidden * d_hidden_d_z1

    def backward(self, features: np.ndarray, targets: np.ndarray, learning_rate: float) -> None:
        """Run backpropagation and update weights and biases in place.

        Must be called after forward() with the same `features`, since it
        reuses the cached hidden and output activations from that call.

        Args:
            features: The same input array passed to the preceding
                forward() call, shape (n_samples, 6).
            targets: True target values, shape (n_samples, 1).
            learning_rate: Gradient descent step size.
        """
        delta_output = self._output_layer_delta(targets)
        delta_hidden = self._hidden_layer_delta(delta_output)

        d_w2 = self.hidden_activation.T @ delta_output
        d_b2 = np.sum(delta_output, axis=0, keepdims=True)
        d_w1 = features.T @ delta_hidden
        d_b1 = np.sum(delta_hidden, axis=0, keepdims=True)

        # Gradient descent update.
        self.w1 -= learning_rate * d_w1
        self.b1 -= learning_rate * d_b1
        self.w2 -= learning_rate * d_w2
        self.b2 -= learning_rate * d_b2

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """Return the network's raw output (probability-like score).

        Args:
            features: Input feature array, shape (n_samples, 6).

        Returns:
            Predicted scores in (0, 1), shape (n_samples, 1).
        """
        return self.forward(features)

    def predict(self, features: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Return binary predictions using a probability threshold.

        Args:
            features: Input feature array, shape (n_samples, 6).
            threshold: Decision threshold applied to predict_proba().

        Returns:
            Binary predictions (0.0 or 1.0), shape (n_samples, 1).
        """
        return (self.predict_proba(features) >= threshold).astype(float)

    def get_params(self) -> dict:
        """Return a copy of the current weights and biases."""
        return {
            "w1": self.w1.copy(),
            "b1": self.b1.copy(),
            "w2": self.w2.copy(),
            "b2": self.b2.copy(),
        }

    def set_params(self, params: dict) -> None:
        """Restore weights and biases from a previously saved copy."""
        self.w1 = params["w1"].copy()
        self.b1 = params["b1"].copy()
        self.w2 = params["w2"].copy()
        self.b2 = params["b2"].copy()


def mse_loss(targets: np.ndarray, predictions: np.ndarray) -> float:
    """Compute Mean Squared Error between targets and predictions."""
    return float(np.mean((predictions - targets) ** 2))


class Dataset(NamedTuple):
    """Bundles the standardized train/test feature and target arrays."""

    x_train: np.ndarray
    y_train: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray


def run_epoch(model: TwoLayerNeuralNetwork, data: Dataset, learning_rate: float) -> tuple:
    """Run one training epoch: forward, backward, and test-set evaluation.

    Args:
        model: The network being trained.
        data: The train/test arrays for this run.
        learning_rate: Gradient descent step size.

    Returns:
        A tuple of (train_mse, test_mse, test_accuracy) for this epoch.
    """
    train_output = model.forward(data.x_train)
    train_mse = mse_loss(data.y_train, train_output)
    model.backward(data.x_train, data.y_train, learning_rate)

    test_output = model.forward(data.x_test)
    test_mse = mse_loss(data.y_test, test_output)
    test_predictions = (test_output >= 0.5).astype(float)
    test_accuracy = float(np.mean(test_predictions == data.y_test))

    return train_mse, test_mse, test_accuracy


def train_model(
    model: TwoLayerNeuralNetwork,
    data: Dataset,
    learning_rate: float,
    max_epochs: int,
    patience: int,
) -> tuple:
    """Train the network with full-batch gradient descent and early stopping.

    Args:
        model: The TwoLayerNeuralNetwork to train.
        data: The standardized train/test feature and target arrays.
        learning_rate: Gradient descent step size.
        max_epochs: Maximum number of training epochs.
        patience: Number of consecutive epochs without test MSE
            improvement before stopping early.

    Returns:
        A tuple of (history dict, best_epoch, best_test_mse).
    """
    history = {"epoch": [], "train_mse": [], "test_mse": [], "test_accuracy": []}
    best_test_mse = np.inf
    best_epoch = 0
    best_params = model.get_params()
    epochs_without_improvement = 0

    print("=== Section 4: Train the Model Until Test MSE Stops Improving ===")

    for epoch in range(1, max_epochs + 1):
        train_mse, test_mse, test_accuracy = run_epoch(model, data, learning_rate)

        history["epoch"].append(epoch)
        history["train_mse"].append(train_mse)
        history["test_mse"].append(test_mse)
        history["test_accuracy"].append(test_accuracy)

        if test_mse < best_test_mse:
            best_test_mse = test_mse
            best_epoch = epoch
            best_params = model.get_params()
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if epoch % 100 == 0:
            print(
                f"Epoch {epoch:5d} | Train MSE: {train_mse:.6f} | "
                f"Test MSE: {test_mse:.6f} | Test Accuracy: {test_accuracy:.4f}"
            )

        if epochs_without_improvement >= patience:
            print(
                f"\nEarly stopping at epoch {epoch}: test MSE has not "
                f"improved for {patience} consecutive epochs."
            )
            break

    model.set_params(best_params)
    print()

    return history, best_epoch, best_test_mse


def evaluate_final_model(
    model: TwoLayerNeuralNetwork,
    data: Dataset,
    best_epoch: int,
    best_test_mse: float,
    filtered_row_count: int,
) -> tuple:
    """Compute and print final evaluation metrics using the best parameters.

    Args:
        model: The trained network, with best parameters already restored.
        data: The standardized train/test feature and target arrays.
        best_epoch: Epoch at which the best test MSE was achieved.
        best_test_mse: The best test MSE achieved during training.
        filtered_row_count: Number of rows remaining after Section 1's
            filtering, for reference in the final report.

    Returns:
        A tuple of (train_accuracy, test_accuracy).
    """
    train_predictions = model.predict(data.x_train)
    test_predictions = model.predict(data.x_test)
    train_accuracy = float(np.mean(train_predictions == data.y_train))
    test_accuracy = float(np.mean(test_predictions == data.y_test))

    print("=== Section 5: Evaluate the Final Model ===")
    print(f"Best epoch: {best_epoch}")
    print(f"Best test MSE: {best_test_mse:.6f}")
    print(f"Final training accuracy: {train_accuracy:.4f}")
    print(f"Final test accuracy: {test_accuracy:.4f}")
    print(f"Number of rows used after filtering: {filtered_row_count}")
    print(f"Training set size: {data.x_train.shape[0]}")
    print(f"Test set size: {data.x_test.shape[0]}")
    print()

    return train_accuracy, test_accuracy


def plot_mse_curve(history: dict, output_path: Path) -> None:
    """Plot training and test MSE over epochs and save as a PNG.

    Args:
        history: The training history dict returned by train_model().
        output_path: File path to save the resulting PNG to.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(history["epoch"], history["train_mse"], label="Training MSE")
    ax.plot(history["epoch"], history["test_mse"], label="Test MSE")
    ax.set_title("Training and Test MSE over Epochs")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Mean Squared Error")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")
    print()


def build_artificial_applicants() -> pd.DataFrame:
    """Build a small DataFrame of manually specified, contrasting applicants.

    Returns:
        A DataFrame with one row per artificial applicant, including a
        human-readable description and the six model input features.
    """
    return pd.DataFrame(
        [
            {
                "description": "Strong int'l PhD applicant",
                "gpa": 3.95,
                "gre": 335,
                "gre_v": 165,
                "gre_aw": 5.0,
                "ms_vs_phd": 1,
                "international_vs_local": 1,
            },
            {
                "description": "Weaker int'l Masters applicant",
                "gpa": 2.9,
                "gre": 295,
                "gre_v": 145,
                "gre_aw": 3.0,
                "ms_vs_phd": 0,
                "international_vs_local": 1,
            },
            {
                "description": "Strong local Masters applicant",
                "gpa": 3.9,
                "gre": 325,
                "gre_v": 160,
                "gre_aw": 4.5,
                "ms_vs_phd": 0,
                "international_vs_local": 0,
            },
            {
                "description": "Average local PhD applicant",
                "gpa": 3.3,
                "gre": 310,
                "gre_v": 152,
                "gre_aw": 3.5,
                "ms_vs_phd": 1,
                "international_vs_local": 0,
            },
        ]
    )


def evaluate_artificial_applicants(
    model: TwoLayerNeuralNetwork,
    train_medians: np.ndarray,
    train_means: np.ndarray,
    train_stds: np.ndarray,
) -> pd.DataFrame:
    """Run the trained model on manually specified artificial applicants.

    Applies the exact same preprocessing pipeline used for the real data
    (median fill using training statistics, then standardization using
    training statistics) before running predictions.

    Args:
        model: The trained network, with best parameters restored.
        train_medians: Training-set feature medians from Section 2.
        train_means: Training-set feature means from Section 2.
        train_stds: Training-set feature standard deviations from Section 2.

    Returns:
        The artificial-applicant DataFrame with predicted probability,
        predicted label, and predicted status columns appended.
    """
    applicants = build_artificial_applicants()
    raw_features = applicants[FEATURE_COLUMNS].to_numpy(dtype=float)

    # Same preprocessing pipeline as the real data: fill with training
    # medians (a no-op here since these applicants have no missing values),
    # then standardize with training means/standard deviations.
    filled_features = np.where(np.isnan(raw_features), train_medians, raw_features)
    scaled_features = (filled_features - train_means) / train_stds

    predicted_proba = model.predict_proba(scaled_features).flatten()
    predicted_label = model.predict(scaled_features).flatten()

    applicants = applicants.copy()
    applicants["predicted_probability"] = predicted_proba.round(4)
    applicants["predicted_label"] = predicted_label.astype(int)
    applicants["predicted_status"] = np.where(
        predicted_label == 1, "Accepted", "Rejected"
    )

    print("=== Section 7: Test the Model on Artificial Applicants ===")
    print(applicants.to_string(index=False))
    print()

    return applicants


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        The parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Train a two-layer NumPy neural network on Grad Cafe "
        "admissions data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("applicant_data.jsonl"),
        help="Path to the JSON-Lines applicant dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to save output files (e.g. mse_curve.png) to.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the full Module 12 pipeline end to end."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = load_and_prepare_data(args.input)
    filtered_row_count = len(df)

    (
        x_train,
        x_test,
        y_train,
        y_test,
        train_medians,
        train_means,
        train_stds,
    ) = split_and_preprocess(df)
    data = Dataset(x_train=x_train, y_train=y_train, x_test=x_test, y_test=y_test)

    print("=== Section 3: Build a Two-Layer Neural Network in NumPy ===")
    model = TwoLayerNeuralNetwork(
        n_features=len(FEATURE_COLUMNS),
        n_hidden=HIDDEN_UNITS,
        random_seed=RANDOM_SEED,
    )
    print(f"W1 shape: {model.w1.shape}")
    print(f"b1 shape: {model.b1.shape}")
    print(f"W2 shape: {model.w2.shape}")
    print(f"b2 shape: {model.b2.shape}")
    print()

    history, best_epoch, best_test_mse = train_model(
        model,
        data,
        learning_rate=LEARNING_RATE,
        max_epochs=MAX_EPOCHS,
        patience=PATIENCE,
    )

    evaluate_final_model(model, data, best_epoch, best_test_mse, filtered_row_count)

    plot_mse_curve(history, args.output_dir / "mse_curve.png")

    evaluate_artificial_applicants(model, train_medians, train_means, train_stds)


if __name__ == "__main__":
    main()
