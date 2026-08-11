"""
consumer.py
-----------
RabbitMQ worker. Routes tasks to handlers, acks only after DB commit.
"""
import datetime
import json
import logging
import os
import time
import urllib.parse as up

import pika
import psycopg2

from gradcafe_common.amqp import QUEUE, declare_topology

from etl.incremental_scraper import scrape_data
from etl.clean import clean_data
from etl.query_data import get_all_results

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)



# The scraper's date_added field is GradCafe's raw display text, e.g.
# "Jun 06, 2026" — NOT sortable as a plain string (month names don't sort
# chronologically: "Feb 01, 2026" < "Jan 01, 2026" lexicographically).
# Watermark comparisons must go through this parser, never raw string `>`.
_DATE_ADDED_FORMAT = "%b %d, %Y"


def _parse_date_added(date_str: str | None) -> datetime.date | None:
    """Parse a scraped date_added string ("Jun 06, 2026") into a date.

    Also accepts already-ISO ("2026-06-06") values, so previously-stored
    watermarks (written before this fix, in the old raw-string format via
    isoformat() on a date parsed the old way) and freshly-scraped records
    both parse correctly.
    """
    if not date_str:
        return None
    date_str = date_str.strip()
    try:
        return datetime.datetime.strptime(date_str, _DATE_ADDED_FORMAT).date()
    except ValueError:
        pass
    try:
        return datetime.date.fromisoformat(date_str)
    except ValueError:
        log.warning("Could not parse date_added value: %r", date_str)
        return None


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
    since_raw = payload.get("since")
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
        if since_raw is None:
            since_raw = _get_watermark(cur, source)
        since_date = _parse_date_added(since_raw)
        log.info("Scraping since: %s (parsed: %s)", since_raw, since_date)

        raw_records = scrape_data(max_pages=10, output_file=None, start_page=1)
        cleaned = clean_data(raw_records)

        # Filter to records strictly newer than the watermark. Comparison
        # happens on parsed dates, not raw strings — see _parse_date_added.
        if since_date is not None:
            cleaned = [
                rec for rec in cleaned
                if (parsed := _parse_date_added(rec.get("date_added"))) is not None
                and parsed > since_date
            ]

        if not cleaned:
            conn.commit()
            log.info("No new records past watermark.")
            return

        max_seen_date = since_date
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
            rec_date = _parse_date_added(rec.get("date_added"))
            if rec_date is not None and (max_seen_date is None or rec_date > max_seen_date):
                max_seen_date = rec_date

        if max_seen_date is not None:
            # Store as ISO so every future read is unambiguous and
            # sortable, regardless of the scraper's raw display format.
            _set_watermark(cur, source, max_seen_date.isoformat())
    conn.commit()
    log.info("Inserted %d records.", len(cleaned))


def handle_recompute_analytics(conn, _payload: dict) -> None:
    """Recompute analytics summary table within a transaction and commit."""
    log.info("Recomputing analytics...")
    with conn.cursor() as cur:
        # Refresh materialized view if present
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
        # Update analytics_cache table so UI reflects latest results
        cur.execute("""
            INSERT INTO analytics_cache (key, computed_at)
            VALUES ('last_recompute', now())
            ON CONFLICT (key) DO UPDATE
                SET computed_at = EXCLUDED.computed_at;
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
    except (psycopg2.DatabaseError, OSError, RuntimeError, ValueError, KeyError) as exc:
        log.error("Handler error for '%s': %s", kind, exc)
        if conn:
            conn.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        if conn:
            conn.close()


def main():  # pragma: no cover
    """Start the RabbitMQ consumer loop with retry on any failure."""
    url = os.environ["RABBITMQ_URL"]
    params = pika.URLParameters(url)

    while True:
        conn = None
        try:
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            declare_topology(ch)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue=QUEUE, on_message_callback=_on_message)
            log.info("Worker ready on queue '%s'...", QUEUE)
            ch.start_consuming()
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError,
                pika.exceptions.ConnectionClosedByBroker,
                pika.exceptions.StreamLostError) as exc:
            log.warning("Connection lost: %s — retrying in 5s...", exc)
            time.sleep(5)
        except (KeyboardInterrupt, SystemExit):
            log.info("Worker shutting down.")
            break
        finally:
            if conn and not conn.is_closed:
                try:
                    conn.close()
                except (pika.exceptions.AMQPError, OSError):
                    pass


if __name__ == "__main__":  # pragma: no cover
    main()
