"""
app.py
------
Flask web application. Buttons publish tasks to RabbitMQ and return 202.
"""
from __future__ import annotations

import os

import pika
import psycopg2
from flask import Flask, current_app, jsonify, render_template

from app.query_data import get_all_results
from publisher import publish_task


def _get_query_fn(flask_app):
    """Resolve query function from injection or real module."""
    fn = flask_app.config.get("QUERY_FN")
    return fn if fn is not None else get_all_results


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
        except (pika.exceptions.AMQPError, OSError, RuntimeError, KeyError) as exc:
            current_app.logger.exception("Failed to publish scrape_new_data")
            return jsonify({"error": "publish_failed", "message": str(exc)}), 503

    @flask_app.route("/api/update_analysis", methods=["POST"])
    def api_update_analysis():
        """Enqueue recompute_analytics task. Returns 202 immediately."""
        try:
            publish_task("recompute_analytics", payload={})
            return jsonify({"status": "queued", "task": "recompute_analytics"}), 202
        except (pika.exceptions.AMQPError, OSError, RuntimeError, KeyError) as exc:
            current_app.logger.exception("Failed to publish recompute_analytics")
            return jsonify({"error": "publish_failed", "message": str(exc)}), 503

    @flask_app.route("/api/scrape_status")
    def api_scrape_status():
        """Worker manages state — return placeholder."""
        return jsonify({"status": "worker_managed"})

    return flask_app


if __name__ == "__main__":  # pragma: no cover
    app = create_app()
    app.run(host="0.0.0.0", port=8080)
