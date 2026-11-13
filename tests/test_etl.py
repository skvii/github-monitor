"""Tests voor de ETL-stappen. GitHub wordt nagebootst met respx: geen echte calls."""

import asyncio
from datetime import UTC, datetime

import httpx
import respx

from github_monitor.db import connect
from github_monitor.etl import GITHUB_EVENTS_URL, extract, load, repo_events_url, transform

NOW = datetime(2026, 11, 13, 10, 0, 0, tzinfo=UTC)


def make_event(event_id: str, event_type: str, repo: str = "owner/repo") -> dict:
    return {
        "id": event_id,
        "type": event_type,
        "actor": {"login": "someone"},
        "repo": {"name": repo},
        "payload": {"action": "opened"},
        "created_at": "2026-11-13T09:55:00Z",
    }


# ---------------------------------------------------------------- Transform


def test_transform_keeps_only_the_three_event_types():
    raw = [
        make_event("1", "WatchEvent"),
        make_event("2", "PushEvent"),  # moet eruit
        make_event("3", "PullRequestEvent"),
        make_event("4", "IssuesEvent"),
        make_event("5", "CreateEvent"),  # moet eruit
    ]
    rows = transform(raw, ingested_at=NOW)
    assert [row["id"] for row in rows] == ["1", "3", "4"]


def test_transform_flattens_an_event_into_one_row():
    rows = transform([make_event("1", "PullRequestEvent")], ingested_at=NOW)
    assert rows == [
        {
            "id": "1",
            "type": "PullRequestEvent",
            "repo_name": "owner/repo",
            "actor_login": "someone",
            "action": "opened",
            "created_at": "2026-11-13T09:55:00Z",
            "ingested_at": "2026-11-13T10:00:00Z",
        }
    ]


# ---------------------------------------------------------------- Load


def test_load_skips_events_we_already_have():
    conn = connect(":memory:")
    rows = transform([make_event("1", "WatchEvent"), make_event("2", "IssuesEvent")], NOW)

    assert load(conn, rows) == 2  # eerste keer: beide nieuw
    assert load(conn, rows) == 0  # tweede keer (overlappende poll): niets nieuw
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2


# ---------------------------------------------------------------- Extract


@respx.mock
def test_extract_returns_events_etag_and_poll_interval():
    respx.get(GITHUB_EVENTS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[make_event("1", "WatchEvent")],
            headers={"ETag": '"abc"', "X-Poll-Interval": "60"},
        )
    )

    async def run():
        async with httpx.AsyncClient() as client:
            return await extract(client, GITHUB_EVENTS_URL, etag=None)

    result = asyncio.run(run())
    assert len(result.events) == 1
    assert result.etag == '"abc"'
    assert result.poll_interval == 60


@respx.mock
def test_extract_sends_etag_and_handles_304_not_modified():
    route = respx.get(GITHUB_EVENTS_URL).mock(
        return_value=httpx.Response(304, headers={"X-Poll-Interval": "60"})
    )

    async def run():
        async with httpx.AsyncClient() as client:
            return await extract(client, GITHUB_EVENTS_URL, etag='"abc"')

    result = asyncio.run(run())
    assert route.calls.last.request.headers["If-None-Match"] == '"abc"'
    assert result.events == []  # niets nieuws
    assert result.etag == '"abc"'  # oude ETag blijft geldig


@respx.mock
def test_extract_can_fetch_events_of_one_repository():
    route = respx.get("https://api.github.com/repos/fastapi/fastapi/events").mock(
        return_value=httpx.Response(200, json=[make_event("1", "PullRequestEvent")])
    )

    async def run():
        async with httpx.AsyncClient() as client:
            return await extract(client, repo_events_url("fastapi/fastapi"), etag=None)

    result = asyncio.run(run())
    assert route.called
    assert result.events[0]["type"] == "PullRequestEvent"
