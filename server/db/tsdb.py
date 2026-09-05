import time
import logging
from typing import Dict, Any, List
from .connection import get_connection

logger = logging.getLogger(__name__)

def enqueue_tsdb_spool(payload: str, max_records: int = 10000) -> bool:
    """Enqueues Prometheus exposition metrics text payload to persistent SQLite disk buffer."""
    if not payload or not payload.strip():
        return False
    now = int(time.time())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO tsdb_spool_queue (payload, created_at, attempts) VALUES (?, ?, 0);",
            (payload.strip(), now)
        )
        # FIFO backpressure eviction if queue exceeds max_records
        count = conn.execute("SELECT COUNT(*) FROM tsdb_spool_queue;").fetchone()[0]
        if count > max_records:
            excess = count - max_records
            conn.execute("""
                DELETE FROM tsdb_spool_queue WHERE id IN (
                    SELECT id FROM tsdb_spool_queue ORDER BY id ASC LIMIT ?
                );
            """, (excess,))
        conn.commit()
    return True

def dequeue_tsdb_spool(batch_size: int = 50) -> List[Dict[str, Any]]:
    """Retrieves the oldest queued TSDB payloads for retry delivery."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, payload, created_at, attempts
            FROM tsdb_spool_queue
            ORDER BY id ASC
            LIMIT ?;
        """, (batch_size,)).fetchall()
        return [{"id": r["id"], "payload": r["payload"], "created_at": r["created_at"], "attempts": r["attempts"]} for r in rows]

def delete_tsdb_spool_entries(ids: List[int]) -> int:
    """Removes successfully delivered payload entries from SQLite disk spool queue."""
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    with get_connection() as conn:
        cursor = conn.execute(f"DELETE FROM tsdb_spool_queue WHERE id IN ({placeholders});", ids)
        conn.commit()
        return cursor.rowcount

def increment_tsdb_spool_attempts(ids: List[int]) -> None:
    """Increments retry attempt counter for payloads that failed delivery."""
    if not ids:
        return
    placeholders = ",".join("?" for _ in ids)
    with get_connection() as conn:
        conn.execute(f"UPDATE tsdb_spool_queue SET attempts = attempts + 1 WHERE id IN ({placeholders});", ids)
        conn.commit()

def get_tsdb_spool_count() -> int:
    """Returns the total number of pending spooled TSDB payload batches."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM tsdb_spool_queue;").fetchone()
        return row[0] if row else 0

def clear_tsdb_spool_queue() -> None:
    """Purges all entries from the disk spool queue."""
    with get_connection() as conn:
        conn.execute("DELETE FROM tsdb_spool_queue;")
        conn.commit()
