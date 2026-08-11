"""
amqp.py
-------
Shared RabbitMQ topology used by both the web publisher and the worker
consumer. Both sides declare it idempotently (durable, safe to redeclare)
since either the publisher or the consumer may start first.
"""
EXCHANGE = "tasks"
QUEUE = "tasks_q"
ROUTING_KEY = "tasks"


def declare_topology(channel) -> None:
    """Idempotently declare the durable exchange, queue, and binding used
    for task messages."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=ROUTING_KEY)
