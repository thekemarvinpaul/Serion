"""
Database setup for Serion's ledger.

Plain SQLite for now. This is deliberately simple — the point of this
layer is that it's boring and auditable, not clever. The AI never
touches this file directly; it only calls functions in models.py,
which call this.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "serion.db"


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contribution_amount REAL NOT NULL,
    frequency_days INTEGER NOT NULL DEFAULT 7
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL REFERENCES cycles(id),
    late_fine REAL NOT NULL DEFAULT 0,
    loan_cap REAL NOT NULL DEFAULT 0,
    quorum INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cycle_members (
    cycle_id INTEGER NOT NULL REFERENCES cycles(id),
    member_id INTEGER NOT NULL REFERENCES members(id),
    PRIMARY KEY (cycle_id, member_id)
);

CREATE TABLE IF NOT EXISTS payment_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL REFERENCES cycles(id),
    payer_id INTEGER NOT NULL REFERENCES members(id),
    receiver_id INTEGER NOT NULL REFERENCES members(id),
    amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | confirmed | partial | disputed
    source TEXT NOT NULL DEFAULT 'voice',    -- voice | text | receipt
    claimed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ballots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL REFERENCES cycles(id),
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',  -- open | closed
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ballot_id INTEGER NOT NULL REFERENCES ballots(id),
    voter_id INTEGER NOT NULL REFERENCES members(id),
    choice TEXT NOT NULL,  -- yes | no
    voted_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (ballot_id, voter_id)
);

CREATE TABLE IF NOT EXISTS confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_claim_id INTEGER NOT NULL REFERENCES payment_claims(id),
    confirmed_by INTEGER NOT NULL REFERENCES members(id),
    confirmed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DB_PATH}")
