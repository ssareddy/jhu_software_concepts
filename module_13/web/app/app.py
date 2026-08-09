"""
app.py
------
Flask web application. Buttons publish tasks to RabbitMQ and return 202.
Also serves the "Will You Get In?" admissions prediction page (Module 13),
backed by a fine-tuned DistilBERT model loaded once at app startup.
"""
from __future__ import annotations

import json
import logging
import os

import psycopg2
from flask import Flask, current_app, jsonify, render_template, request

from app.query_data import get_all_results
from publisher import publish_task

try:
    from inference import AdmissionsPredictor
except ImportError:  # pragma: no cover - inference.py should always be present
    AdmissionsPredictor = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loaded ONCE at process startup, not per-request. This is what
# satisfies the "SHALL NOT retrain / reload from scratch every time the
# page is loaded" requirement -- every prediction request reuses this
# same in-memory predictor instance.
# ---------------------------------------------------------------------------
_predictor = None
_predictor_load_error = None

if AdmissionsPredictor is not None:
    try:
        _predictor = AdmissionsPredictor()
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        # We deliberately do NOT crash the whole Flask app if the model isn't
        # trained/saved yet -- the Analysis page should still work. The
        # "Will You Get In?" page will show a friendly message instead.
        _predictor_load_error = str(exc)
        logger.warning("Could not load admissions model at startup: %s", exc)


def _get_query_fn(flask_app):
    """Resolve query function from injection or real module."""
    fn = flask_app.config.get("QUERY_FN")
    return fn if fn is not None else get_all_results


def _clean_form_value(raw):
    """Best-effort clean of a single submitted form field: strips whitespace,
    treats blank strings as missing. Never raises."""
    if raw is None:
        return None
    val = str(raw).strip()
    return val if val != "" else None


def create_app(query_fn=None):
    """Application factory."""
    flask_app = Flask(__name__, template_folder="templates", static_folder="static")
    flask_app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "")
    flask_app.config["RABBITMQ_URL"] = os.environ.get("RABBITMQ_URL", "")
    flask_app.config["QUERY_FN"] = query_fn

    @flask_app.route("/")
    def index():
        """Render the main analysis page."""
        return render_template("index.html")

    @flask_app.route("/analysis")
    def analysis():
        """Alias for index."""
        return render_template("index.html")

    @flask_app.route("/api/results")
    def api_results():
        """Return all query results as JSON."""
        try:
            data = _get_query_fn(flask_app)()
            return jsonify({"status": "ok", "data": data})
        except (psycopg2.DatabaseError, OSError, RuntimeError) as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

    @flask_app.route("/api/pull_data", methods=["POST"])
    def api_pull_data():
        """Enqueue scrape_new_data task. Returns 202 immediately."""
        try:
            publish_task("scrape_new_data", payload={})
            return jsonify({"status": "queued", "task": "scrape_new_data"}), 202
        except (OSError, RuntimeError) as exc:
            current_app.logger.exception("Failed to publish scrape_new_data")
            return jsonify({"error": "publish_failed", "message": str(exc)}), 503

    @flask_app.route("/api/update_analysis", methods=["POST"])
    def api_update_analysis():
        """Enqueue recompute_analytics task. Returns 202 immediately."""
        try:
            publish_task("recompute_analytics", payload={})
            return jsonify({"status": "queued", "task": "recompute_analytics"}), 202
        except (OSError, RuntimeError) as exc:
            current_app.logger.exception("Failed to publish recompute_analytics")
            return jsonify({"error": "publish_failed", "message": str(exc)}), 503

    @flask_app.route("/api/scrape_status")
    def api_scrape_status():
        """Worker manages state — return placeholder."""
        return jsonify({"status": "worker_managed"})

    # -----------------------------------------------------------------
    # Module 13: "Will You Get In?" admissions prediction page
    # -----------------------------------------------------------------

    @flask_app.route("/will-you-get-in")
    def will_you_get_in():
        """Render the blank prediction form."""
        return render_template(
            "will_you_get_in.html",
            model_unavailable=(_predictor is None),
        )

    @flask_app.route("/api/predict", methods=["POST"])
    def api_predict():
        """
        Collect submitted applicant fields, convert them into the same
        unified text format used during training, run the fine-tuned
        model, and return the prediction + confidence score.

        Never crashes on missing/blank/malformed input, and never exposes
        raw stack traces to the client.
        """
        if _predictor is None:
            return jsonify({
                "status": "error",
                "message": (
                    "The prediction model is not currently available on this "
                    "server. Run train_model.py to train and save a model, "
                    "then restart the app."
                ),
            }), 503

        try:
            payload = request.get_json(silent=True) or request.form

            applicant = {
                "program": _clean_form_value(payload.get("program")),
                "university": _clean_form_value(payload.get("university")),
                "comments": _clean_form_value(payload.get("comments")),
                "term": _clean_form_value(payload.get("term")),
                "degree": _clean_form_value(payload.get("degree")),
                "citizenship": _clean_form_value(payload.get("citizenship")),
                "gpa": _clean_form_value(payload.get("gpa")),
                "gre": _clean_form_value(payload.get("gre")),
                "gre_v": _clean_form_value(payload.get("gre_v")),
                "gre_aw": _clean_form_value(payload.get("gre_aw")),
            }

            # Graceful numeric validation: if a numeric field was submitted
            # but isn't actually a valid number, treat it as missing rather
            # than crashing or passing garbage into the model.
            for numeric_field in ("gpa", "gre", "gre_v", "gre_aw"):
                val = applicant[numeric_field]
                if val is not None:
                    try:
                        float(val)
                    except (TypeError, ValueError):
                        applicant[numeric_field] = None

            result = _predictor.predict(applicant)

            return jsonify({
                "status": "ok",
                "prediction": result["prediction"],
                "score": result["score"],
                "prob_accepted": result["prob_accepted"],
            })

        except (RuntimeError, ValueError, KeyError, AttributeError, OSError):
            current_app.logger.exception("Prediction failed")
            return jsonify({
                "status": "error",
                "message": (
                    "Something went wrong generating a prediction. "
                    "Please check your inputs and try again."
                ),
            }), 500

    return flask_app


if __name__ == "__main__":  # pragma: no cover
    app = create_app()
    app.run(host="0.0.0.0", port=8080)
