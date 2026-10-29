"""Opening the database and creating the tables."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "event_tracker.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores links between tables without this
    return conn


def init_db(conn):
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


# Spots left = capacity minus sign-ups. LEFT JOIN keeps events with zero sign-ups.
EVENTS_WITH_SPOTS = """
SELECT e.event_id, e.title, e.capacity,
       COUNT(s.signup_id) AS signed_up,
       e.capacity - COUNT(s.signup_id) AS spots_left
FROM events e
LEFT JOIN signups s ON s.event_id = e.event_id
GROUP BY e.event_id
ORDER BY e.starts_at
"""

if __name__ == "__main__":
    c = connect()
    init_db(c)
    print("Database ready at", DB_PATH)
