-- Event Tracker schema (Step 1). Safe to run more than once.
-- Times are stored as UTC text like 2026-10-02T22:00:00Z (same as the API),
-- because text in that fixed format sorts correctly.

-- Who runs events: clubs, the school, community groups.
CREATE TABLE IF NOT EXISTS organisers (
    organiser_id  INTEGER PRIMARY KEY,
    external_id   INTEGER UNIQUE,            -- the API's id; NULL for ones we create ourselves
    name          TEXT NOT NULL,
    type          TEXT NOT NULL CHECK (type IN ('club', 'school', 'community')),
    contact_email TEXT
);

-- Each event belongs to exactly one organiser (NOT NULL + REFERENCES).
CREATE TABLE IF NOT EXISTS events (
    event_id      INTEGER PRIMARY KEY,
    external_id   INTEGER UNIQUE,
    organiser_id  INTEGER NOT NULL REFERENCES organisers(organiser_id),
    title         TEXT NOT NULL,
    description   TEXT,
    venue         TEXT,
    starts_at     TEXT NOT NULL,
    ends_at       TEXT NOT NULL,
    capacity      INTEGER NOT NULL CHECK (capacity > 0),
    category      TEXT,
    CHECK (ends_at >= starts_at)
);
CREATE INDEX IF NOT EXISTS idx_events_organiser ON events(organiser_id);
CREATE INDEX IF NOT EXISTS idx_events_starts_at ON events(starts_at);

-- One row per person per event. Spots left is calculated, never stored.
CREATE TABLE IF NOT EXISTS signups (
    signup_id      INTEGER PRIMARY KEY,
    event_id       INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    email          TEXT NOT NULL CHECK (email = lower(email)),
    signed_up_at   TEXT NOT NULL,
    origin         TEXT NOT NULL DEFAULT 'local' CHECK (origin IN ('local', 'communityhub')),
    reference_code TEXT UNIQUE,              -- the API's EXT-000187; NULL for local sign-ups
    source         TEXT,                     -- where on CommunityHub it came from
    UNIQUE (event_id, email),                -- same email cannot join the same event twice
    CHECK ((origin = 'communityhub') = (reference_code IS NOT NULL))
);
