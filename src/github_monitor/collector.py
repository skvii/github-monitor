"""De collector: draait de ETL-pipeline steeds opnieuw, zolang de app draait.

Bronnen: altijd heel GitHub (/events), plus optioneel een lijst repo's
(/repos/{owner}/{repo}/events) zodat de PR-statistiek per repo genoeg data heeft.

Deze module weet niets van de API. Daardoor kan hij later ook als los proces draaien.
"""

import asyncio
import logging
import sqlite3

import httpx

from github_monitor.etl import GITHUB_EVENTS_URL, extract, load, repo_events_url, transform, utc_now

logger = logging.getLogger(__name__)


async def run_collector(conn: sqlite3.Connection, token: str | None, repos: list[str]) -> None:
    """Oneindige lus: voor elke bron ophalen -> structureren -> opslaan, dan wachten."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.warning("Geen GITHUB_TOKEN gezet: maximaal 60 requests per uur.")

    sources = [GITHUB_EVENTS_URL] + [repo_events_url(repo) for repo in repos]
    etags: dict[str, str | None] = {url: None for url in sources}  # één ETag per bron

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        while True:
            wait_seconds = 60
            for url in sources:
                try:
                    result = await extract(client, url, etags[url])
                    etags[url] = result.etag
                    # Houd de langste wachttijd aan die GitHub over alle bronnen opgeeft.
                    wait_seconds = max(wait_seconds, result.poll_interval)

                    rows = transform(result.events, ingested_at=utc_now())
                    saved = load(conn, rows)
                    logger.info(
                        "%s -> opgehaald: %d, relevant: %d, nieuw opgeslagen: %d",
                        url,
                        len(result.events),
                        len(rows),
                        saved,
                    )
                except httpx.HTTPError as error:
                    # Netwerkfout, rate limit (403), onbekende repo (404) of storing bij
                    # GitHub: loggen en bij de volgende ronde opnieuw proberen.
                    logger.error("Ophalen mislukt voor %s: %s", url, error)

            await asyncio.sleep(wait_seconds)
