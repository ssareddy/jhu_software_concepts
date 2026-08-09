"""
Module 13 - Scale & LM Deployment Assignment
inference.py

Helper code to reload the fine-tuned DistilBERT admissions model (saved by
train_model.py) and run predictions on new applicant data, without any
retraining. Used both for the Section 6 reload demonstration below and by
the Flask "Will You Get In?" webpage (Section 7).
"""

import json
import os

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from model_common import build_unified_text

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_model", "final_model")


class AdmissionsPredictor:
    """Loads the fine-tuned model once and exposes a .predict() method.
    Intended to be instantiated a single time at Flask app startup, NOT
    re-created on every request -- this is what satisfies the assignment's
    'SHALL NOT retrain / reload from scratch on every page visit' requirement."""

    def __init__(self, model_dir: str = MODEL_DIR):
        if not os.path.isdir(model_dir):
            raise FileNotFoundError(
                f"No saved model found at '{model_dir}'. Run train_model.py first."
            )

        with open(os.path.join(model_dir, "metadata.json"), encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        self.model.to(self.device)
        self.model.eval()
        self.max_length = self.metadata.get("max_length", 256)
        self.label_mapping = self.metadata.get("label_mapping", {"0": "Rejected", "1": "Accepted"})

    def model_info(self) -> dict:
        """Return a small diagnostic summary of the loaded model.

        Useful for a health-check endpoint or debugging, without needing
        to run a full prediction.

        Returns:
            A dict with the model name, device, max sequence length, and
            label mapping currently loaded.
        """
        return {
            "model_name": self.metadata.get("model_name"),
            "device": self.device,
            "max_length": self.max_length,
            "label_mapping": self.label_mapping,
        }

    def predict(self, applicant: dict) -> dict:
        """
        applicant: dict with keys program, university, comments, term, degree,
                   citizenship, gpa, gre, gre_v, gre_aw (any may be missing/blank).
        returns: {"prediction": "Accepted"|"Rejected", "score": float, "input_text": str}
        """
        text = build_unified_text(applicant)

        with torch.no_grad():
            enc = self.tokenizer(
                text,
                truncation=True,
                padding="max_length",
                max_length=self.max_length,
                return_tensors="pt",
            )
            enc = {k: v.to(self.device) for k, v in enc.items()}
            logits = self.model(**enc).logits
            probs = torch.softmax(logits, dim=1).squeeze()
            pred_idx = int(torch.argmax(probs).item())

        return {
            "prediction": self.label_mapping[str(pred_idx)],
            "score": round(float(probs[pred_idx].item()), 4),
            "prob_accepted": round(float(probs[1].item()), 4),
            "input_text": text,
        }


def main() -> None:
    """Demonstrate reloading the saved model and running inference on
    two examples, with no retraining -- Section 6's required output."""
    print("=" * 70)
    print("SECTION 6 (continued): Reload the Saved Model and Run Inference")
    print("=" * 70)

    predictor = AdmissionsPredictor()
    print(f"Reloaded model + tokenizer from: {MODEL_DIR}")
    print(f"Label mapping: {predictor.label_mapping}")
    print()

    examples = [
        {
            "program": "Computer Science",
            "university": "Stanford University",
            "comments": (
                "Strong research background, two publications, "
                "3 years of ML research experience."
            ),
            "term": "Fall 2026",
            "degree": "PhD",
            "citizenship": "International",
            "gpa": "3.95",
            "gre": "170",
            "gre_v": "165",
            "gre_aw": "5.0",
        },
        {
            "program": "History",
            "university": "Unknown",
            "comments": "",
            "term": "Fall 2026",
            "degree": "Master's",
            "citizenship": "American",
            "gpa": "2.8",
            "gre": "",
            "gre_v": "",
            "gre_aw": "",
        },
    ]

    for i, ex in enumerate(examples, 1):
        result = predictor.predict(ex)
        print(f"Example {i}:")
        print(result["input_text"])
        print(f"  --> Prediction: {result['prediction']} | Model score: {result['score']}")
        print()


if __name__ == "__main__":
    main()
