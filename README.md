# Event Tracker (Step 1: database and starter data)

## Set up
1. Create a virtual environment and install packages:
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
2. Copy .env.example to .env and put your own API key in it.

## Create the database and load the starter data
python -m scripts.load_starter_data
(creates event_tracker.db from db/schema.sql, then loads the data; safe to run twice)

## Run the tests
pytest

## Files
- db/schema.sql: the tables (organisers, events, signups)
- db/database.py: opens the database, turns foreign keys on
- scripts/load_starter_data.py: loads the CommunityHub starter data
- tests/: automated tests
- docs/architecture.png: architecture diagram
