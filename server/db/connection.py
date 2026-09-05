import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "one_state.db"))
active_path = os.path.abspath(DB_PATH)

@contextmanager
def get_connection():
    from . import DB_PATH
    conn = sqlite3.connect(os.path.abspath(DB_PATH), timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
