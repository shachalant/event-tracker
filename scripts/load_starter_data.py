"""Load the CommunityHub starter data into our database.

Run from the project folder:   python -m scripts.load_starter_data
Safe to run more than once: rows are matched on the API's ids, so nothing doubles up.
"""
import os
import re
import sys
import time
from datetime import datetime

from db.database import connect, init_db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_RE = re.compile(r"^EXT-\d{6}$")
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ORGANISER_TYPES = {"club", "school", "community"}


def fetch_sample_data():
    import requests
    from dotenv import load_dotenv

    load_dotenv()
    key = os.environ.get("API_KEY")
    base = os.environ.get("API_BASE_URL", "").rstrip("/")
    if not key or not base:
        sys.exit("Set API_KEY and API_BASE_URL in your .env file.")
    for _ in range(3):
        r = requests.get(f"{base}/v1/sample-data", headers={"X-API-Key": key}, timeout=60)
        if r.status_code == 429:  # too many requests: wait as long as the API says
            time.sleep(int(r.headers.get("Retry-After", "5")))
            continue
        r.raise_for_status()
        return r.json()
    sys.exit("Still rate limited after 3 tries. Wait a minute and run again.")


def parse_time(value):
    try:
        return datetime.strptime(value, TIME_FORMAT)
    except (TypeError, ValueError):
        return None


def clean_email(value):
    email = value.strip().lower() if isinstance(value, str) else ""
    return email if EMAIL_RE.match(email) else None


def text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def load(conn, data):
    """Insert organisers, then events, then sign-ups. Returns counts and skip reasons."""
    stats = {"organisers": 0, "events": 0, "signups": 0, "skipped": []}
    org_ids, event_ids = {}, {}  # API id -> our id

    with conn:  # one transaction: all or nothing
        for o in data.get("organisers", []):
            name, kind = text(o.get("name")), o.get("type")
            if not name or kind not in ORGANISER_TYPES or not isinstance(o.get("id"), int):
                stats["skipped"].append(f"organiser {o.get('id')}: bad name, type or id")
                continue
            conn.execute(
                """INSERT INTO organisers (external_id, name, type, contact_email)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(external_id) DO UPDATE SET
                     name = excluded.name, type = excluded.type,
                     contact_email = excluded.contact_email""",
                (o["id"], name, kind, clean_email(o.get("contact_email"))),
            )
            org_ids[o["id"]] = conn.execute(
                "SELECT organiser_id FROM organisers WHERE external_id = ?", (o["id"],)
            ).fetchone()[0]
            stats["organisers"] += 1

        for e in data.get("events", []):
            start, end = parse_time(e.get("starts_at")), parse_time(e.get("ends_at"))
            cap = e.get("capacity")
            problem = None
            if not isinstance(e.get("id"), int) or not text(e.get("title")):
                problem = "missing id or title"
            elif e.get("organiser_id") not in org_ids:
                problem = "unknown organiser"
            elif not start or not end or end < start:
                problem = "bad or out-of-order dates"
            elif not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
                problem = "capacity must be a whole number above zero"
            if problem:
                stats["skipped"].append(f"event {e.get('id')}: {problem}")
                continue
            conn.execute(
                """INSERT INTO events (external_id, organiser_id, title, description, venue,
                                       starts_at, ends_at, capacity, category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(external_id) DO UPDATE SET
                     organiser_id = excluded.organiser_id, title = excluded.title,
                     description = excluded.description, venue = excluded.venue,
                     starts_at = excluded.starts_at, ends_at = excluded.ends_at,
                     capacity = excluded.capacity, category = excluded.category""",
                (e["id"], org_ids[e["organiser_id"]], text(e["title"]), text(e.get("description")),
                 text(e.get("venue")), e["starts_at"], e["ends_at"], cap, text(e.get("category"))),
            )
            event_ids[e["id"]] = conn.execute(
                "SELECT event_id FROM events WHERE external_id = ?", (e["id"],)
            ).fetchone()[0]
            stats["events"] += 1

        for s in sorted(data.get("signups", []),
                        key=lambda s: s.get("signed_up_at") or s.get("signup_time") or ""):
            code, email = s.get("reference_code"), clean_email(s.get("email"))
            when = s.get("signed_up_at") or s.get("signup_time")
            problem = None
            if not isinstance(code, str) or not CODE_RE.match(code):
                problem = "bad reference code"
            elif s.get("event_id") not in event_ids:
                problem = "unknown event"
            elif not text(s.get("name")):
                problem = "missing name"
            elif not email:
                problem = "invalid email"
            elif not parse_time(when):
                problem = "bad signup time"
            if problem:
                stats["skipped"].append(f"signup {code}: {problem}")
                continue
            try:
                conn.execute(
                    """INSERT INTO signups (event_id, name, email, signed_up_at, origin,
                                            reference_code, source)
                       VALUES (?, ?, ?, ?, 'communityhub', ?, ?)
                       ON CONFLICT(reference_code) DO UPDATE SET
                         name = excluded.name, email = excluded.email,
                         signed_up_at = excluded.signed_up_at, source = excluded.source""",
                    (event_ids[s["event_id"]], text(s["name"]), email, when,
                     code, text(s.get("source"))),
                )
                stats["signups"] += 1
            except Exception as err:  # e.g. same email already on that event under another code
                stats["skipped"].append(f"signup {code}: {err}")
    return stats


def over_capacity(conn):
    return conn.execute(
        """SELECT e.title, e.capacity, COUNT(*) AS n FROM events e
           JOIN signups s ON s.event_id = e.event_id
           GROUP BY e.event_id HAVING n > e.capacity"""
    ).fetchall()


def main():
    conn = connect()
    init_db(conn)
    stats = load(conn, fetch_sample_data())
    print(f"Loaded {stats['organisers']} organisers, {stats['events']} events, "
          f"{stats['signups']} sign-ups.")
    for line in stats["skipped"]:
        print("  skipped:", line)
    for row in over_capacity(conn):
        print(f"  note: '{row['title']}' has {row['n']} sign-ups for capacity {row['capacity']}")


if __name__ == "__main__":
    main()
