"""De statistieken: gewone SQL-queries op de events-tabel.

`now` wordt meegegeven in plaats van binnen de functie opgevraagd. Zo kunnen tests
de klok vastzetten.
"""

import sqlite3
from datetime import datetime, timedelta

from github_monitor.config import EVENT_TYPES


def to_iso(moment: datetime) -> str:
    """Zelfde formaat als GitHub: '2026-11-13T09:50:00Z'. Zo kunnen we tekst vergelijken."""
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def count_events_by_type(conn: sqlite3.Connection, offset_minutes: int, now: datetime) -> dict:
    """Aantal events per type, aangemaakt (op GitHub) in de laatste `offset_minutes` minuten."""
    since = to_iso(now - timedelta(minutes=offset_minutes))
    rows = conn.execute(
        "SELECT type, COUNT(*) AS n FROM events WHERE created_at >= ? GROUP BY type",
        (since,),
    ).fetchall()

    # GROUP BY laat types zonder events weg: die vullen we aan met 0.
    counts = {event_type: 0 for event_type in EVENT_TYPES}
    for row in rows:
        counts[row["type"]] = row["n"]

    return {
        "offset_minutes": offset_minutes,
        "since": since,
        "counts": counts,
        "total": sum(counts.values()),
    }


def average_time_between_pull_requests(
    conn: sqlite3.Connection, repo: str, action: str | None = None
) -> dict:
    """Gemiddelde tijd tussen PullRequestEvents voor één repository.

    Zonder `action` tellen alle PR-events mee; met bv. action="opened" alleen nieuwe PR's.
    Het gemiddelde van de tussentijden = (laatste - eerste) / (aantal - 1).
    """
    query = """
        SELECT COUNT(*) AS n, MIN(created_at) AS first, MAX(created_at) AS last
        FROM events
        WHERE type = 'PullRequestEvent' AND repo_name = ?
    """
    params: list[str] = [repo]
    if action:
        query += " AND action = ?"
        params.append(action)
    row = conn.execute(query, params).fetchone()

    count = row["n"]
    result = {"repo": repo, "action": action or "all", "pull_request_events": count}
    if count < 2:
        # Minder dan 2 events: er is geen tussentijd. Geen fout, wel geen getal.
        return {**result, "avg_seconds": None}

    first = datetime.fromisoformat(row["first"])
    last = datetime.fromisoformat(row["last"])
    avg_seconds = (last - first).total_seconds() / (count - 1)
    return {**result, "avg_seconds": round(avg_seconds, 1)}


def events_per_minute(conn: sqlite3.Connection, offset_minutes: int, now: datetime) -> dict:
    """Aantal events per minuut per type, voor de grafiek (zie 07-visualisatie.md)."""
    start = (now - timedelta(minutes=offset_minutes)).replace(second=0, microsecond=0)
    rows = conn.execute(
        """
        SELECT substr(created_at, 1, 16) AS minute, type, COUNT(*) AS n
        FROM events
        WHERE created_at >= ?
        GROUP BY minute, type
        """,
        (to_iso(start),),
    ).fetchall()

    # Elke minuut in het venster krijgt een plek, ook als er niets gebeurde (dan 0).
    # Anders trekt de grafiek een rechte lijn over een gat heen.
    minutes = []
    moment = start
    while moment <= now:
        minutes.append(moment.strftime("%Y-%m-%dT%H:%M"))
        moment += timedelta(minutes=1)

    series = {event_type: [0] * len(minutes) for event_type in EVENT_TYPES}
    position = {minute: i for i, minute in enumerate(minutes)}
    for row in rows:
        if row["minute"] in position:
            series[row["type"]][position[row["minute"]]] = row["n"]

    return {"minutes": minutes, "series": series}
