"""De ETL-pipeline: Extract (GitHub) -> Transform (filteren, plat maken) -> Load (SQLite).

Elke stap is een losse functie, zodat je ze apart kunt lezen en testen.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from github_monitor.config import EVENT_TYPES

GITHUB_EVENTS_URL = "https://api.github.com/events"  # publieke events van heel GitHub


def repo_events_url(repo: str) -> str:
    """Events van één repository, bv. 'fastapi/fastapi'."""
    return f"https://api.github.com/repos/{repo}/events"


# ---------------------------------------------------------------- Extract


@dataclass
class ExtractResult:
    events: list[dict]  # ruwe events zoals GitHub ze teruggeeft (leeg bij 304)
    etag: str | None  # meesturen bij de volgende call
    poll_interval: int  # zoveel seconden wachten voor de volgende call


async def extract(client: httpx.AsyncClient, url: str, etag: str | None) -> ExtractResult:
    """Haal de nieuwste events op bij GitHub (heel GitHub of één repo, afhankelijk van url).

    Met de ETag vragen we "is er iets nieuws?". Is het antwoord 304 (niets nieuws),
    dan telt die call niet mee voor de rate limit.
    """
    headers = {"If-None-Match": etag} if etag else {}
    response = await client.get(url, params={"per_page": 100}, headers=headers)

    poll_interval = int(response.headers.get("X-Poll-Interval", 60))

    if response.status_code == 304:
        return ExtractResult(events=[], etag=etag, poll_interval=poll_interval)

    response.raise_for_status()  # 403/5xx -> exception, de collector vangt die af
    return ExtractResult(
        events=response.json(),
        etag=response.headers.get("ETag"),
        poll_interval=poll_interval,
    )


# ---------------------------------------------------------------- Transform


def transform(raw_events: list[dict], ingested_at: datetime) -> list[dict]:
    """Houd alleen onze drie eventtypes over en maak elk event plat (één rij per event).

    Dit is een pure functie: geen netwerk, geen database. Daardoor makkelijk te testen.
    """
    ingested = ingested_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for event in raw_events:
        if event.get("type") not in EVENT_TYPES:
            continue
        rows.append(
            {
                "id": event["id"],
                "type": event["type"],
                "repo_name": event["repo"]["name"],
                "actor_login": (event.get("actor") or {}).get("login"),
                "action": (event.get("payload") or {}).get("action"),
                "created_at": event["created_at"],  # GitHub levert al UTC: '...Z'
                "ingested_at": ingested,
            }
        )
    return rows


# ---------------------------------------------------------------- Load


def load(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Sla rijen op. Events die we al hebben (zelfde id) worden overgeslagen.

    Geeft het aantal nieuw opgeslagen events terug.
    """
    before = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO events
            (id, type, repo_name, actor_login, action, created_at, ingested_at)
        VALUES
            (:id, :type, :repo_name, :actor_login, :action, :created_at, :ingested_at)
        """,
        rows,
    )
    conn.commit()
    return conn.total_changes - before


def utc_now() -> datetime:
    return datetime.now(UTC)
