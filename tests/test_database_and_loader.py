import sqlite3

import pytest

from db.database import connect, init_db, EVENTS_WITH_SPOTS
from scripts.load_starter_data import load


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


def sample():
    """Made-up data in the same shape the API documentation shows."""
    return {
        "organisers": [{"id": 1, "name": "Test Robotics Club", "type": "club",
                        "contact_email": "hello@example.org"}],
        "events": [{"id": 10, "organiser_id": 1, "title": "Robot Night", "description": "Fun",
                    "venue": "Room 2", "starts_at": "2026-10-02T22:00:00Z",
                    "ends_at": "2026-10-03T00:00:00Z", "capacity": 2, "category": "technology"}],
        "signups": [{"reference_code": "EXT-000001", "event_id": 10, "name": "Sam Example",
                     "email": "sam@example.org", "signed_up_at": "2026-09-20T10:00:00Z",
                     "source": "CommunityHub App"}],
    }


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_empty_database_has_no_events(conn):
    assert conn.execute(EVENTS_WITH_SPOTS).fetchall() == []


def test_event_without_signups_has_all_spots_free(conn):
    data = sample()
    data["signups"] = []
    load(conn, data)
    row = conn.execute(EVENTS_WITH_SPOTS).fetchone()
    assert (row["signed_up"], row["spots_left"]) == (0, 2)


def test_spots_left_counts_signups(conn):
    load(conn, sample())
    assert conn.execute(EVENTS_WITH_SPOTS).fetchone()["spots_left"] == 1


def test_loading_twice_makes_no_duplicates(conn):
    load(conn, sample())
    before = [count(conn, t) for t in ("organisers", "events", "signups")]
    load(conn, sample())
    assert [count(conn, t) for t in ("organisers", "events", "signups")] == before == [1, 1, 1]


@pytest.mark.parametrize("field,value", [
    ("email", "not-an-email"), ("email", ""), ("signed_up_at", "yesterday"),
    ("reference_code", "EXT-12"), ("name", "  "), ("event_id", 999),
])
def test_bad_signup_is_skipped_not_loaded(conn, field, value):
    data = sample()
    data["signups"][0][field] = value
    stats = load(conn, data)
    assert count(conn, "signups") == 0 and len(stats["skipped"]) == 1


@pytest.mark.parametrize("field,value", [
    ("starts_at", "02/10/2026"), ("ends_at", "2026-10-01T00:00:00Z"),
    ("capacity", 0), ("capacity", -5), ("capacity", "24"), ("organiser_id", 99),
])
def test_bad_event_is_skipped_not_loaded(conn, field, value):
    data = sample()
    data["events"][0][field] = value
    load(conn, data)
    assert count(conn, "events") == 0


def test_email_is_cleaned_to_lowercase(conn):
    data = sample()
    data["signups"][0]["email"] = "  SAM@Example.org "
    load(conn, data)
    assert conn.execute("SELECT email FROM signups").fetchone()[0] == "sam@example.org"


def test_database_refuses_same_email_twice_for_one_event(conn):
    load(conn, sample())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""INSERT INTO signups (event_id, name, email, signed_up_at)
                        VALUES (1, 'Sam Again', 'sam@example.org', '2026-09-21T10:00:00Z')""")


def test_database_refuses_event_for_missing_organiser(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""INSERT INTO events (organiser_id, title, starts_at, ends_at, capacity)
                        VALUES (42, 'Ghost', '2026-10-02T22:00:00Z', '2026-10-03T00:00:00Z', 5)""")


def test_deleting_event_removes_its_signups(conn):
    load(conn, sample())
    conn.execute("DELETE FROM events")
    assert count(conn, "signups") == 0
