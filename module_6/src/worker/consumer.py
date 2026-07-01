"""
consumer.py
-----------
RabbitMQ worker. Routes tasks to handlers, acks only after DB commit.
"""
import json
import logging
import os
import time
import urllib.parse as up

import pika
import psycopg2

from etl.incremental_scraper import scrape_data
from etl.clean import clean_data
from etl.query_data import get_all_results

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

EXCHANGE = "tasks"
QUEUE = "tasks_q"
ROUTING_KEY = "tasks"


def _parse_float(val):
    """Convert value to float or None."""
    try:
        return float(val) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _open_db():
    """Open psycopg2 connection from DATABASE_URL."""
    url = os.environ["DATABASE_URL"]
    parsed = up.urlparse(url)
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password or "",
    )


def _get_watermark(cur, source: str):
    """Read last_seen watermark for a source."""
    cur.execute(
        "SELECT last_seen FROM ingestion_watermarks WHERE source = %s LIMIT 1;",
        (source,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _set_watermark(cur, source: str, last_seen: str) -> None:
    """Advance the watermark after successful inserts."""
    cur.execute(
        """
        INSERT INTO ingestion_watermarks (source, last_seen)
        VALUES (%s, %s)
        ON CONFLICT (source) DO UPDATE
            SET last_seen = EXCLUDED.last_seen, updated_at = now();
        """,
        (source, last_seen),
    )


def handle_scrape_new_data(conn, payload: dict) -> None:
    """Scrape, clean, and insert new records idempotently with watermark."""
    source = "gradcafe"
    since = payload.get("since")
    insert_sql = """
        INSERT INTO applicants (
            program, comments, date_added, url, status, term,
            us_or_international, gpa, gre, gre_v, gre_aw, degree,
            llm_generated_program, llm_generated_university
        ) VALUES (
            %(program)s, %(comments)s, %(date_added)s, %(url)s, %(status)s,
            %(term)s, %(us_or_international)s, %(gpa)s, %(gre)s, %(gre_v)s,
            %(gre_aw)s, %(degree)s, %(llm_generated_program)s,
            %(llm_generated_university)s
        ) ON CONFLICT (url) DO NOTHING;
    """
    with conn.cursor() as cur:
        if since is None:
            since = _get_watermark(cur, source)
        log.info("Scraping since: %s", since)
        raw_records = scrape_data(max_pages=10, output_file=None, start_page=1)
        cleaned = clean_data(raw_records)
        if not cleaned:
            conn.commit()
            return
        last_seen = None
        for rec in cleaned:
            cur.execute(insert_sql, {
                "program": rec.get("program"),
                "comments": rec.get("comments"),
                "date_added": rec.get("date_added"),
                "url": rec.get("url"),
                "status": rec.get("status"),
                "term": rec.get("term"),
                "us_or_international": rec.get("US/International"),
                "gpa": _parse_float(rec.get("GPA")),
                "gre": _parse_float(rec.get("GRE")),
                "gre_v": _parse_float(rec.get("GRE V")),
                "gre_aw": _parse_float(rec.get("GRE AW")),
                "degree": rec.get("Degree"),
                "llm_generated_program": rec.get("llm-generated-program"),
                "llm_generated_university": rec.get("llm-generated-university"),
            })
            if rec.get("date_added"):
                last_seen = rec["date_added"]
        if last_seen:
            _set_watermark(cur, source, last_seen)
    conn.commit()
    log.info("Inserted %d records.", len(cleaned))


def handle_recompute_analytics(conn, _payload: dict) -> None:
    """Recompute analytics within a transaction and commit."""
    log.info("Recomputing analytics...")
    with conn.cursor() as cur:
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_matviews WHERE matviewname = 'analytics_summary'
                ) THEN
                    REFRESH MATERIALIZED VIEW analytics_summary;
                END IF;
            END $$;
        """)
    conn.commit()
    get_all_results()
    log.info("Analytics recomputed.")


TASK_MAP = {
    "scrape_new_data": handle_scrape_new_data,
    "recompute_analytics": handle_recompute_analytics,
}


def _on_message(ch, method, _properties, body):
    """Parse message, route to handler, ack on success, nack on error."""
    try:
        message = json.loads(body)
        kind = message.get("kind", "")
        payload = message.get("payload", {})
        log.info("Received task: %s", kind)
    except (json.JSONDecodeError, KeyError) as exc:
        log.error("Malformed message: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    handler = TASK_MAP.get(kind)
    if handler is None:
        log.warning("Unknown task '%s' — discarding.", kind)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    conn = None
    try:
        conn = _open_db()
        handler(conn, payload)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        log.info("Task '%s' acknowledged.", kind)
    except (psycopg2.DatabaseError, OSError, RuntimeError) as exc:
        log.error("Handler error for '%s': %s", kind, exc)
        if conn:
            conn.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        if conn:
            conn.close()


def main():  # pragma: no cover
    """Start the RabbitMQ consumer loop with retry on connection failure."""
    url = os.environ["RABBITMQ_URL"]
    params = pika.URLParameters(url)

    while True:
        try:
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
            ch.queue_declare(queue=QUEUE, durable=True)
            ch.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=ROUTING_KEY)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue=QUEUE, on_message_callback=_on_message)
            log.info("Worker ready on queue '%s'...", QUEUE)
            ch.start_consuming()
        except pika.exceptions.AMQPConnectionError as exc:
            log.warning("Connection failed: %s — retrying in 5s...", exc)
            time.sleep(5)


if __name__ == "__main__":  # pragma: no cover
    main()
