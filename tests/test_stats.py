"""Tests voor de statistieken. De klok staat vast op NOW, zodat de uitkomst voorspelbaar is."""

from datetime import UTC, datetime

from github_monitor import stats
from github_monitor.db import connect

NOW = datetime(2026, 11, 13, 10, 0, 0, tzinfo=UTC)


def make_db(events: list[tuple[str, str, str, str]]):
    """events: (id, type, repo_name, created_at)"""
    conn = connect(":memory:")
    conn.executemany(
        "INSERT INTO events (id, type, repo_name, created_at, ingested_at) "
        "VALUES (?, ?, ?, ?, '2026-11-13T10:00:00Z')",
        events,
    )
    return conn


# ---------------------------------------------------------------- Offset


def test_count_by_type_only_counts_events_within_offset():
    conn = make_db(
        [
            ("1", "WatchEvent", "a/a", "2026-11-13T09:55:00Z"),  # 5 min geleden -> telt
            ("2", "WatchEvent", "a/a", "2026-11-13T09:50:00Z"),  # precies 10 min -> telt
            ("3", "IssuesEvent", "a/a", "2026-11-13T09:49:59Z"),  # net te oud -> telt niet
        ]
    )
    result = stats.count_events_by_type(conn, offset_minutes=10, now=NOW)

    assert result["since"] == "2026-11-13T09:50:00Z"
    assert result["counts"] == {"WatchEvent": 2, "PullRequestEvent": 0, "IssuesEvent": 0}
    assert result["total"] == 2


def test_count_by_type_always_returns_all_three_types():
    result = stats.count_events_by_type(make_db([]), offset_minutes=10, now=NOW)
    assert result["counts"] == {"WatchEvent": 0, "PullRequestEvent": 0, "IssuesEvent": 0}


# ---------------------------------------------------------------- PR-tijd


def test_average_time_between_pull_requests():
    # Voorbeeld uit beslissing 05: 10:00, 10:10, 10:30, 11:00 -> tussentijden 10, 20, 30 min
    conn = make_db(
        [
            ("1", "PullRequestEvent", "x/y", "2026-11-13T10:00:00Z"),
            ("2", "PullRequestEvent", "x/y", "2026-11-13T10:10:00Z"),
            ("3", "PullRequestEvent", "x/y", "2026-11-13T10:30:00Z"),
            ("4", "PullRequestEvent", "x/y", "2026-11-13T11:00:00Z"),
            ("5", "PullRequestEvent", "other/repo", "2026-11-13T10:05:00Z"),  # andere repo
            ("6", "WatchEvent", "x/y", "2026-11-13T10:20:00Z"),  # ander type
        ]
    )
    result = stats.average_time_between_pull_requests(conn, "x/y")

    assert result["pull_request_events"] == 4
    assert result["avg_seconds"] == 20 * 60  # gemiddeld 20 minuten


def test_average_time_is_none_with_fewer_than_two_events():
    conn = make_db([("1", "PullRequestEvent", "x/y", "2026-11-13T10:00:00Z")])
    result = stats.average_time_between_pull_requests(conn, "x/y")
    assert result == {
        "repo": "x/y",
        "action": "all",
        "pull_request_events": 1,
        "avg_seconds": None,
    }


# ---------------------------------------------------------------- Per minuut


def test_events_per_minute_fills_empty_minutes_with_zero():
    conn = make_db(
        [
            ("1", "WatchEvent", "a/a", "2026-11-13T09:58:10Z"),
            ("2", "WatchEvent", "a/a", "2026-11-13T09:58:40Z"),
            ("3", "IssuesEvent", "a/a", "2026-11-13T10:00:00Z"),
        ]
    )
    result = stats.events_per_minute(conn, offset_minutes=3, now=NOW)

    assert result["minutes"] == [
        "2026-11-13T09:57",
        "2026-11-13T09:58",
        "2026-11-13T09:59",
        "2026-11-13T10:00",
    ]
    assert result["series"]["WatchEvent"] == [0, 2, 0, 0]
    assert result["series"]["IssuesEvent"] == [0, 0, 0, 1]
    assert result["series"]["PullRequestEvent"] == [0, 0, 0, 0]


def test_average_time_can_filter_on_action():
    # 3 PR-events, waarvan 2 'opened' (10:00 en 11:00) en 1 'labeled' (10:30)
    conn = connect(":memory:")
    conn.executemany(
        "INSERT INTO events (id, type, repo_name, action, created_at, ingested_at) "
        "VALUES (?, 'PullRequestEvent', 'x/y', ?, ?, '2026-11-13T12:00:00Z')",
        [
            ("1", "opened", "2026-11-13T10:00:00Z"),
            ("2", "labeled", "2026-11-13T10:30:00Z"),
            ("3", "opened", "2026-11-13T11:00:00Z"),
        ],
    )
    all_events = stats.average_time_between_pull_requests(conn, "x/y")
    only_opened = stats.average_time_between_pull_requests(conn, "x/y", action="opened")

    assert all_events["avg_seconds"] == 30 * 60  # 3 events in 60 min -> elke 30 min
    assert only_opened["avg_seconds"] == 60 * 60  # 2 nieuwe PR's in 60 min -> elke 60 min
    assert only_opened["action"] == "opened"
