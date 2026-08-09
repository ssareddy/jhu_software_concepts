"""
Module 13 - Scale & LM Deployment Assignment
train_model.py

Loads the cleaned Grad Cafe admissions dataset, builds a unified text
representation per applicant, splits into train/test, fine-tunes a
pretrained DistilBERT model for binary Accepted/Rejected classification,
evaluates it, and saves the model for later inference from the Flask app.
"""

import argparse
import json
import os
import random
import time
from typing import NamedTuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from model_common import UNIFIED_TEMPLATE, format_value

RANDOM_STATE = 42
random.seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)
torch.manual_seed(RANDOM_STATE)

DATA_PATH = "cleaned_gradcafe.json"
OUTPUT_DIR = "saved_model"

# ---------------------------------------------------------------------------
# Section 4 configuration
# ---------------------------------------------------------------------------
# Recommended baseline configuration (used by default -- run this on your own
# hardware for the full, non-subsampled training run). All of these are
# overridable from the command line; see the --sample_size flag in particular,
# which lets you run a fast subsampled "proof of pipeline" pass on constrained
# hardware (e.g. this assignment's dev sandbox, 1 CPU core / no GPU) without
# touching any other code.
MODEL_NAME = "distilbert-base-uncased"
TOKENIZER_NAME = "distilbert-base-uncased"
DEFAULT_MAX_LENGTH = 256
DEFAULT_BATCH_SIZE = 8
DEFAULT_EPOCHS = 3
DEFAULT_LR = 2e-5
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ---------------------------------------------------------------------------
# Section 1: Load and Prepare the Applicant Dataset
# ---------------------------------------------------------------------------

# Fields used for modeling and why:
#
# TEXT FIELDS (>= 2 required):
#   - llm-generated-program      : LLM-cleaned program name (e.g. "Computer Science").
#                                   Cleaner / more consistent than the raw scraped
#                                   `program` or `program_raw` fields.
#   - llm-generated-university   : LLM-cleaned university name, same rationale.
#   - comments                   : Free-text applicant statement / notes. This is the
#                                   richest text signal (research experience, LOR
#                                   quality, self-assessment, etc.) that a two-layer
#                                   NumPy network could never use.
#   - term                       : e.g. "Fall 2026". Short text field capturing
#                                   application cycle context.
#
# NON-TEXT FIELDS (>= 3 required):
#   - Degree                     : categorical (PhD / Masters / etc.)
#   - US/International           : categorical citizenship status
#   - GPA                        : numeric
#   - GRE                        : numeric (combined/quant depending on scrape)
#   - GRE V                      : numeric (verbal)
#   - GRE AW                     : numeric (analytical writing)
#
# This satisfies "at least two text fields" (we use four) and "at least three
# non-text fields" (we use six), and it deliberately reuses the same cleaned
# columns produced in earlier modules rather than re-deriving them.

TEXT_FIELDS = ["llm-generated-program", "llm-generated-university", "comments", "term"]
NONTEXT_FIELDS = ["Degree", "US/International", "GPA", "GRE", "GRE V", "GRE AW"]
NUMERIC_FIELDS = ["GPA", "GRE", "GRE V", "GRE AW"]
CATEGORICAL_FIELDS = ["Degree", "US/International"]


def _has_min_content(row) -> bool:
    """Check whether a row has enough usable information for a valid input.

    Args:
        row: A row from the raw applicant DataFrame.

    Returns:
        True if the row has a usable llm-generated-program value.
    """
    program = row["llm-generated-program"]
    return isinstance(program, str) and program.strip() != ""


def _normalize_missing(value):
    """Normalize a text/categorical field value to a consistent format.

    Args:
        value: A raw field value, which may be None, NaN, or a string.

    Returns:
        "Unknown" if the value is missing/empty, otherwise the stripped
        string form.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Unknown"
    stripped = str(value).strip()
    return "Unknown" if stripped == "" else stripped


def load_and_prepare_data(path=DATA_PATH):
    """Load, filter, deduplicate, and clean the applicant dataset.

    Args:
        path: Path to the cleaned Grad Cafe JSON dataset.

    Returns:
        The cleaned, filtered DataFrame with a "label" column added.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    df = pd.DataFrame(raw)
    n_original = len(df)

    # --- keep only Accepted / Rejected -------------------------------------------------
    df = df[df["outcome"].isin(["Accepted", "Rejected"])].copy()

    # --- remove duplicate applicant rows referring to the same entry URL ---------------
    df = df.drop_duplicates(subset="url", keep="first")

    # --- require enough usable info to build a valid input ------------------------------
    # An applicant row is only usable if it has a usable program value in the
    # required text fields; llm-generated-program is always populated in this
    # cleaned dataset when the row is otherwise usable.
    df = df[df.apply(_has_min_content, axis=1)].copy()

    # --- normalize missing values into a consistent format ------------------------------
    for col in TEXT_FIELDS + CATEGORICAL_FIELDS:
        df[col] = df[col].apply(_normalize_missing)

    # --- convert numeric columns to numeric types where appropriate ---------------------
    for col in NUMERIC_FIELDS:
        df[col] = pd.to_numeric(df[col], errors="coerce")  # NaN = missing, handled at template time

    # --- create target variable ----------------------------------------------------------
    df["label"] = (df["outcome"] == "Accepted").astype(int)

    n_filtered = len(df)
    n_accepted = int((df["label"] == 1).sum())
    n_rejected = int((df["label"] == 0).sum())

    print("=" * 70)
    print("SECTION 1: Dataset Loading, Filtering, and Field Selection")
    print("=" * 70)
    print(f"Rows in original dataset:        {n_original}")
    print(f"Rows remaining after filtering:  {n_filtered}")
    print(f"Accepted rows:                   {n_accepted}")
    print(f"Rejected rows:                   {n_rejected}")
    print()
    print(f"Text fields used ({len(TEXT_FIELDS)}):     {TEXT_FIELDS}")
    print(f"Non-text fields used ({len(NONTEXT_FIELDS)}): {NONTEXT_FIELDS}")
    print()
    print("Preview of cleaned dataframe (relevant columns):")
    preview_cols = TEXT_FIELDS + NONTEXT_FIELDS + ["outcome", "label"]
    print(df[preview_cols].head(5).to_string())
    print()

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Section 2: Convert Each Applicant into a Unified Model Input
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Section 2: Convert Each Applicant into a Unified Model Input
# ---------------------------------------------------------------------------
# format_value() and UNIFIED_TEMPLATE now live in model_common.py, imported
# above, so this exact same logic is shared with inference.py (and the
# Flask app that uses it) instead of being duplicated and risking drift.


def build_unified_text(row):
    """
    Converts a single applicant row into one consistent, human-readable text
    block. This function is used identically at both training time and
    inference time (from the Flask form), and it never includes the
    Accepted/Rejected label -- only the input features -- so the target
    can never leak into the representation.
    """
    return UNIFIED_TEMPLATE.format(
        program=format_value(row["llm-generated-program"]),
        university=format_value(row["llm-generated-university"]),
        comments=format_value(row["comments"]),
        term=format_value(row["term"]),
        degree=format_value(row["Degree"]),
        citizenship=format_value(row["US/International"]),
        gpa=format_value(row["GPA"]),
        gre=format_value(row["GRE"]),
        gre_v=format_value(row["GRE V"]),
        gre_aw=format_value(row["GRE AW"]),
    )


def add_unified_text(df):
    """Build and print the unified text representation for every row.

    Args:
        df: Cleaned DataFrame from load_and_prepare_data().

    Returns:
        df with a new "model_input_text" column added.
    """
    df = df.copy()
    df["model_input_text"] = df.apply(build_unified_text, axis=1)

    print("=" * 70)
    print("SECTION 2: Unified Model Input")
    print("=" * 70)
    print("Template used for every applicant:")
    print("-" * 70)
    print(UNIFIED_TEMPLATE)
    print("-" * 70)
    print()
    print("Three sample model inputs from the training dataset:")
    for _, row in df.sample(3, random_state=RANDOM_STATE).iterrows():
        label_str = "Accepted" if row["label"] == 1 else "Rejected"
        print("-" * 40)
        print(row["model_input_text"])
        print(f"[label = {row['label']} ({label_str})]")
    print()

    return df


# ---------------------------------------------------------------------------
# Section 3: Train / Test Split
# ---------------------------------------------------------------------------

def split_data(df):
    """Split into stratified train/test sets and print required Section 3 output.

    Args:
        df: Cleaned DataFrame with a "label" column and "model_input_text".

    Returns:
        A tuple of (train_df, test_df), each with a reset index.
    """
    train_df, test_df = train_test_split(
        df,
        test_size=0.2,
        random_state=RANDOM_STATE,
        shuffle=True,
        stratify=df["label"],
    )

    train_balance = train_df["label"].value_counts(normalize=True).rename(
        {0: "Rejected", 1: "Accepted"}
    )
    test_balance = test_df["label"].value_counts(normalize=True).rename(
        {0: "Rejected", 1: "Accepted"}
    )

    print("=" * 70)
    print("SECTION 3: Train / Test Split")
    print("=" * 70)
    print(f"Training set size: {len(train_df)}")
    print(f"Test set size:     {len(test_df)}")
    print()
    print("Class balance in training set:")
    print(train_balance)
    print()
    print("Class balance in test set:")
    print(test_balance)
    print()
    print(
        "Why train/test separation matters: the test set stands in for real "
        "future applicants -- exactly the people who will use the deployed "
        "'Will You Get In?' webpage. If we evaluated on rows the model "
        "already trained on, our reported accuracy/precision/recall would "
        "be optimistic and would not reflect how the model behaves on a "
        "brand-new user's input at deployment time. A held-out test set is "
        "our best available proxy for that real-world, public-facing "
        "behavior."
    )
    print()

    return train_df.reset_index(drop=True), test_df.reset_index(drop=True)


class AdmissionsDataset(Dataset):
    """Wraps tokenized unified-text inputs + binary labels for PyTorch."""

    def __init__(self, texts, labels, tokenizer, max_length):
        self.encodings = tokenizer(
            list(texts),
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        self.labels = torch.tensor(list(labels), dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


# ---------------------------------------------------------------------------
# Section 4: Fine-Tune a Pretrained PyTorch Language Model
# ---------------------------------------------------------------------------

class TrainingConfig(NamedTuple):
    """Bundles the Section 4 training hyperparameters."""

    max_length: int
    batch_size: int
    epochs: int
    lr: float


def _subsample_for_demo(train_df, test_df, sample_size):
    """Subsample train/test sets for a fast hardware-constrained demo run.

    Args:
        train_df: Full training DataFrame.
        test_df: Full test DataFrame.
        sample_size: Target number of training rows to keep.

    Returns:
        A tuple of (subsampled train_df, subsampled test_df).
    """
    train_df = train_df.sample(
        n=min(sample_size, len(train_df)), random_state=RANDOM_STATE
    ).reset_index(drop=True)
    eval_sample = max(20, sample_size // 4)
    test_df = test_df.sample(
        n=min(eval_sample, len(test_df)), random_state=RANDOM_STATE
    ).reset_index(drop=True)
    print(
        f"NOTE: running on a hardware-constrained SUBSAMPLE "
        f"(train n={len(train_df)}, test n={len(test_df)}) to demonstrate "
        "that the full training pipeline (tokenization -> DataLoader -> "
        "training loop -> optimizer step -> validation) works correctly "
        "end-to-end on constrained hardware. Re-run this exact script with "
        "--sample_size 0 to train on the full dataset, with no other code "
        "changes required."
    )
    return train_df, test_df


def _print_training_config(config: TrainingConfig) -> None:
    """Print the required Section 4 configuration output.

    Args:
        config: The training hyperparameters for this run.
    """
    print()
    print("Model configuration:")
    print(f"  model name:        {MODEL_NAME}")
    print(f"  tokenizer name:    {TOKENIZER_NAME}")
    print(f"  max sequence len:  {config.max_length}")
    print(f"  batch size:        {config.batch_size}")
    print(f"  epochs:            {config.epochs}")
    print(f"  learning rate:     {config.lr}")
    print("  optimizer:         AdamW")
    print(f"  device:            {DEVICE}")
    print(
        "  tokenizer choice:  distilbert-base-uncased's WordPiece "
        "tokenizer is used because it exactly matches the pretrained "
        "DistilBERT checkpoint's vocabulary. DistilBERT retains ~97% of "
        "BERT's language understanding while being ~40% smaller and ~60% "
        "faster, which is why it (and its matching tokenizer) is the "
        "recommended choice for fine-tuning on ordinary/limited hardware, "
        "per the assignment guidance and the linked HF fine-tuning "
        "article."
    )
    print()


def _build_data_loaders(train_df, test_df, tokenizer, config: TrainingConfig):
    """Build tokenized PyTorch datasets and dataloaders for train/test.

    Args:
        train_df: Training DataFrame with a "model_input_text" column.
        test_df: Test DataFrame with a "model_input_text" column.
        tokenizer: The Hugging Face tokenizer to use.
        config: Training hyperparameters (uses max_length, batch_size).

    Returns:
        A tuple of (train_loader, test_loader).
    """
    train_dataset = AdmissionsDataset(
        train_df["model_input_text"], train_df["label"], tokenizer, config.max_length
    )
    test_dataset = AdmissionsDataset(
        test_df["model_input_text"], test_df["label"], tokenizer, config.max_length
    )
    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False)
    return train_loader, test_loader


def _print_step_progress(epoch_info, step, train_loader, loss, epoch_start) -> None:
    """Print a periodic training-step progress line.

    Args:
        epoch_info: A (epoch, total_epochs) tuple, both zero-based/counts.
        step: Zero-based index of the current step within this epoch.
        train_loader: DataLoader over the training set (for its length).
        loss: The current step's loss tensor.
        epoch_start: time.time() value when this epoch began.
    """
    epoch, total_epochs = epoch_info
    elapsed = time.time() - epoch_start
    steps_done = step + 1
    secs_per_step = elapsed / steps_done
    eta_secs = secs_per_step * (len(train_loader) - steps_done)
    print(
        f"  Epoch {epoch + 1}/{total_epochs} | "
        f"Step {steps_done}/{len(train_loader)} "
        f"| loss={loss.item():.4f} | {secs_per_step:.2f}s/step "
        f"| ETA this epoch: {eta_secs / 60:.1f} min",
        flush=True,
    )


def _run_training_epoch(model, optimizer, train_loader, epoch, total_epochs) -> None:
    """Run one full training epoch, printing periodic progress logs.

    Args:
        model: The model being trained.
        optimizer: The optimizer to step with.
        train_loader: DataLoader over the training set.
        epoch: Zero-based index of the current epoch.
        total_epochs: Total number of epochs being trained.
    """
    epoch_start = time.time()
    running_loss = 0.0
    log_every = max(1, min(50, len(train_loader) // 10))
    for step, batch in enumerate(train_loader):
        batch = {k: v.to(DEVICE) for k, v in batch.items()}
        optimizer.zero_grad()
        outputs = model(**batch)
        loss = outputs.loss
        loss.backward()
        optimizer.step()
        running_loss += loss.item()

        if step % log_every == 0 or step == len(train_loader) - 1:
            _print_step_progress((epoch, total_epochs), step, train_loader, loss, epoch_start)

    avg_loss = running_loss / len(train_loader)
    elapsed_total = time.time() - epoch_start
    print(
        f"  --> Epoch {epoch + 1} complete | avg training loss={avg_loss:.4f} "
        f"| time={elapsed_total:.1f}s"
    )


def fine_tune_model(train_df, test_df, config: TrainingConfig, sample_size=None):
    """Fine-tune the pretrained model on the training dataset.

    Args:
        train_df: Training DataFrame with a "model_input_text" column.
        test_df: Test DataFrame with a "model_input_text" column.
        config: The training hyperparameters for this run.
        sample_size: If set, subsample train/test for a fast demo run on
            constrained hardware; None trains on the full dataset.

    Returns:
        A tuple of (model, tokenizer, train_loader, test_loader, test_df).
    """
    print("=" * 70)
    print("SECTION 4: Fine-Tuning a Pretrained PyTorch Language Model")
    print("=" * 70)

    if sample_size is not None:
        train_df, test_df = _subsample_for_demo(train_df, test_df, sample_size)
    else:
        print(f"Training on FULL training set: n={len(train_df)}")

    _print_training_config(config)

    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    model.to(DEVICE)

    train_loader, test_loader = _build_data_loaders(train_df, test_df, tokenizer, config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr)

    print("Training output logs:")
    model.train()
    for epoch in range(config.epochs):
        _run_training_epoch(model, optimizer, train_loader, epoch, config.epochs)
    print()

    return model, tokenizer, train_loader, test_loader, test_df


# ---------------------------------------------------------------------------
# Section 5: Evaluate the Final Model
# ---------------------------------------------------------------------------

class EvalResults(NamedTuple):
    """Bundles per-example predictions, true labels, and probabilities."""

    preds: list
    labels: list
    probs: list


def _run_test_predictions(model, test_loader) -> EvalResults:
    """Run the model over the test set and collect predictions/labels/probabilities.

    Args:
        model: The fine-tuned model, already moved to DEVICE.
        test_loader: DataLoader over the tokenized test set.

    Returns:
        An EvalResults with one entry per test example.
    """
    model.eval()
    all_preds, all_labels, all_probs = [], [], []
    with torch.no_grad():
        for batch in test_loader:
            labels = batch.pop("labels").to(DEVICE)
            batch = {k: v.to(DEVICE) for k, v in batch.items()}
            outputs = model(**batch)
            probs = torch.softmax(outputs.logits, dim=1)
            preds = torch.argmax(probs, dim=1)

            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())
            all_probs.extend(probs[:, 1].cpu().tolist())  # P(Accepted)

    return EvalResults(preds=all_preds, labels=all_labels, probs=all_probs)


def _print_metrics_summary(results: EvalResults) -> dict:
    """Compute and print accuracy/precision/recall/F1/confusion matrix.

    Args:
        results: The predictions/labels from _run_test_predictions().

    Returns:
        A dict of the computed metrics, for reuse in the saved metadata.
    """
    acc = accuracy_score(results.labels, results.preds)
    prec = precision_score(results.labels, results.preds, zero_division=0)
    rec = recall_score(results.labels, results.preds, zero_division=0)
    f1 = f1_score(results.labels, results.preds, zero_division=0)
    cm = confusion_matrix(results.labels, results.preds)

    print("Metrics summary:")
    print(f"  Accuracy:  {acc:.4f}")
    print(f"  Precision: {prec:.4f}")
    print(f"  Recall:    {rec:.4f}")
    print(f"  F1:        {f1:.4f}")
    print()
    print("Confusion matrix (rows=actual, cols=predicted) [Rejected, Accepted]:")
    print(cm)
    print()

    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "confusion_matrix": cm.tolist(),
        "n_test": len(results.labels),
    }


def _print_class_distribution(results: EvalResults) -> None:
    """Print actual vs. predicted class counts for the test set."""
    n_accepted_true = sum(results.labels)
    n_rejected_true = len(results.labels) - n_accepted_true
    n_accepted_pred = sum(results.preds)
    n_rejected_pred = len(results.preds) - n_accepted_pred
    print(
        f"Class distribution (test set): actual Accepted={n_accepted_true}, "
        f"actual Rejected={n_rejected_true}"
    )
    print(
        f"Class distribution (predictions): predicted Accepted={n_accepted_pred}, "
        f"predicted Rejected={n_rejected_pred}"
    )
    print()


def _print_probability_examples(results: EvalResults) -> None:
    """Print predicted probability, true label, and prediction for a few examples."""
    print("Probability examples for several predictions:")
    for i in range(min(5, len(results.preds))):
        pred_label = "Accepted" if results.preds[i] == 1 else "Rejected"
        true_label = "Accepted" if results.labels[i] == 1 else "Rejected"
        print(
            f"  P(Accepted)={results.probs[i]:.3f} | "
            f"predicted={pred_label} | actual={true_label}"
        )
    print()


def _print_example_group(indices, label, test_df, results: EvalResults) -> None:
    """Print up to two representative test examples from a group.

    Args:
        indices: Row indices (into test_df/results) belonging to this group.
        label: Heading text, e.g. "Correctly classified examples".
        test_df: The test DataFrame (for the example's input text).
        results: The full predictions/labels/probabilities.
    """
    print(f"{label} ({len(indices)} of {len(results.preds)} total):")
    for i in indices[:2]:
        print("-" * 40)
        print(test_df.iloc[i]["model_input_text"][:200] + "...")
        print(
            f"  predicted={results.preds[i]} actual={results.labels[i]} "
            f"P(Accepted)={results.probs[i]:.3f}"
        )
    print()


def evaluate_model(model, test_loader, test_df) -> dict:
    """Evaluate the fine-tuned model on the held-out test set.

    Args:
        model: The fine-tuned model, already moved to DEVICE.
        test_loader: DataLoader over the tokenized test set.
        test_df: The test DataFrame (for showing example texts).

    Returns:
        A dict of computed evaluation metrics.
    """
    print("=" * 70)
    print("SECTION 5: Final Model Evaluation")
    print("=" * 70)

    results = _run_test_predictions(model, test_loader)
    metrics = _print_metrics_summary(results)
    _print_class_distribution(results)
    _print_probability_examples(results)

    correct_idx = [i for i, pred in enumerate(results.preds) if pred == results.labels[i]]
    incorrect_idx = [i for i, pred in enumerate(results.preds) if pred != results.labels[i]]
    _print_example_group(correct_idx, "Correctly classified examples", test_df, results)
    _print_example_group(incorrect_idx, "Incorrectly classified examples", test_df, results)

    return metrics


# ---------------------------------------------------------------------------
# Section 6: Save and Reload the Trained Model
# ---------------------------------------------------------------------------

def save_model(model, tokenizer, metrics, max_length, output_dir=OUTPUT_DIR):
    """Save the fine-tuned model, tokenizer, and preprocessing metadata.

    Args:
        model: The fine-tuned model.
        tokenizer: The tokenizer used for training.
        metrics: The evaluation metrics dict from evaluate_model().
        max_length: The max sequence length actually used for this run.
        output_dir: Directory to save the model into.

    Returns:
        The path to the saved model directory.
    """
    print("=" * 70)
    print("SECTION 6: Save the Trained Model")
    print("=" * 70)

    final_dir = os.path.join(output_dir, "final_model")
    os.makedirs(final_dir, exist_ok=True)

    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)

    metadata = {
        "label_mapping": {"0": "Rejected", "1": "Accepted"},
        "model_name": MODEL_NAME,
        "tokenizer_name": TOKENIZER_NAME,
        "max_length": max_length,  # actual value used for THIS training run, not the default
        "template": UNIFIED_TEMPLATE,
        "text_fields": TEXT_FIELDS,
        "nontext_fields": NONTEXT_FIELDS,
        "metrics": metrics,
    }
    with open(os.path.join(final_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved model weights, tokenizer, and metadata.json to: {final_dir}/")
    print()
    return final_dir


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        The parsed argument namespace.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sample_size",
        type=int,
        default=150,
        help=(
            "Number of training rows to subsample for a quick "
            "pipeline-verification run on constrained hardware. Pass 0 "
            "to use the FULL training set (recommended on a GPU / more "
            "capable machine)."
        ),
    )
    parser.add_argument("--max_length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--lr", type=float, default=DEFAULT_LR)
    return parser.parse_args()


def main() -> None:
    """Run the full Module 13 data prep, fine-tuning, and save pipeline."""
    args = parse_args()
    sample_size = None if args.sample_size == 0 else args.sample_size

    df = load_and_prepare_data()
    df = add_unified_text(df)
    train_df, test_df = split_data(df)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    train_df.to_json(os.path.join(OUTPUT_DIR, "train_split.json"), orient="records")
    test_df.to_json(os.path.join(OUTPUT_DIR, "test_split.json"), orient="records")

    config = TrainingConfig(
        max_length=args.max_length,
        batch_size=args.batch_size,
        epochs=args.epochs,
        lr=args.lr,
    )
    model, tokenizer, _train_loader, test_loader, eval_test_df = fine_tune_model(
        train_df,
        test_df,
        config,
        sample_size=sample_size,
    )

    metrics = evaluate_model(model, test_loader, eval_test_df)
    final_dir = save_model(model, tokenizer, metrics, max_length=args.max_length)

    print("=" * 70)
    print("TRAINING RUN COMPLETE")
    print("=" * 70)
    print(f"Final model directory: {final_dir}")


if __name__ == "__main__":
    main()
