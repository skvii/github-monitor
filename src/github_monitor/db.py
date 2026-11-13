"""SQLite-database: verbinding openen en tabel aanmaken."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,   -- event-id van GitHub; voorkomt dubbele events
    type        TEXT NOT NULL,      -- WatchEvent | PullRequestEvent | IssuesEvent
    repo_name   TEXT NOT NULL,      -- 'owner/repo'
    actor_login TEXT,               -- wie het deed
    action      TEXT,               -- payload.action, bv. 'opened' of 'started'
    created_at  TEXT NOT NULL,      -- moment op GitHub (UTC)
    ingested_at TEXT NOT NULL       -- moment waarop wij het opsloegen (UTC)
);
CREATE INDEX IF NOT EXISTS idx_events_created ON events (created_at);
CREATE INDEX IF NOT EXISTS idx_events_repo ON events (repo_name, type);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Open de database (maakt het bestand en de tabel aan als die nog niet bestaan)."""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: FastAPI kan de verbinding vanuit een andere thread gebruiken
    # dan waarin hij is geopend. Er is maar één schrijver (de collector), dus dat is veilig.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # rijen benaderen op kolomnaam: row["type"]
    conn.execute("PRAGMA journal_mode=WAL")  # lezen en schrijven tegelijk
    conn.executescript(SCHEMA)
    return conn
