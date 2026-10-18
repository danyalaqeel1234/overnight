"""Deliver committed order events to Redis Streams and archive PDF receipts in MinIO."""
import base64
import io
import json
import logging
import os
import time
import psycopg
import redis
from minio import Minio

logging.basicConfig(level=logging.INFO)


def main():
    cache = redis.Redis.from_url(os.environ["REDIS_URL"])
    objects = Minio(os.environ["MINIO_ENDPOINT"], access_key=os.environ["MINIO_ROOT_USER"], secret_key=os.environ["MINIO_ROOT_PASSWORD"], secure=False)
    bucket = "receipts"
    while True:
        try:
            if not objects.bucket_exists(bucket):
                objects.make_bucket(bucket)
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                rows = conn.execute("SELECT event_id,payload FROM outbox WHERE NOT published FOR UPDATE SKIP LOCKED LIMIT 100").fetchall()
                for eid, payload in rows:
                    row = conn.execute("SELECT payload FROM domain_entities WHERE collection='orders' AND entity_id=%s", (payload["order_id"],)).fetchone()
                    if row and row[0].get("receipt"):
                        pdf = base64.b64decode(row[0]["receipt"]["pdf_base64"])
                        objects.put_object(bucket, payload["order_id"] + ".pdf", io.BytesIO(pdf), len(pdf), content_type="application/pdf")
                    # Outbox delivery is at least once. Consumers deduplicate on event_id.
                    cache.xadd("order-events", {"event_id": eid, "data": json.dumps(payload)})
                    conn.execute("UPDATE outbox SET published=true WHERE event_id=%s", (eid,))
            time.sleep(0.25)
        except Exception:
            logging.exception("Worker will retry pending events")
            time.sleep(2)

if __name__ == "__main__":
    main()
