"""
publisher.py
------------
RabbitMQ publisher for the web service.
"""
import datetime
import json
import os

import pika

from gradcafe_common.amqp import EXCHANGE, ROUTING_KEY, declare_topology


def _open_channel():
    """Connect to RabbitMQ and declare durable exchange, queue, and binding."""
    url = os.environ["RABBITMQ_URL"]
    params = pika.URLParameters(url)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    declare_topology(ch)
    return conn, ch


def publish_task(kind: str, payload: dict | None = None, headers: dict | None = None) -> None:
    """
    Publish a persistent task message to the tasks exchange.

    Raises on failure so the Flask endpoint can return 503.
    """
    body = json.dumps(
        {"kind": kind, "ts": datetime.datetime.utcnow().isoformat(), "payload": payload or {}},
        separators=(",", ":"),
    ).encode("utf-8")

    conn, ch = _open_channel()
    try:
        ch.basic_publish(
            exchange=EXCHANGE,
            routing_key=ROUTING_KEY,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2, headers=headers or {}),
            mandatory=False,
        )
    finally:
        conn.close()
