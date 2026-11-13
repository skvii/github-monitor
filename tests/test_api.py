"""Tests voor de endpoints, met FastAPI's TestClient (geen echte server nodig)."""

import pytest
from fastapi.testclient import TestClient

from github_monitor.api import create_app
from github_monitor.config import Settings


@pytest.fixture
def client(tmp_path):
    # Eigen database per test, en de collector uit: we willen GitHub niet echt aanroepen.
    settings = Settings(
        github_token=None,
        db_path=str(tmp_path / "test.db"),
        collector_enabled=False,
        github_repos=[],
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_events_endpoint_returns_counts_for_all_types(client):
    response = client.get("/stats/events", params={"offset": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["offset_minutes"] == 10
    assert set(body["counts"]) == {"WatchEvent", "PullRequestEvent", "IssuesEvent"}


@pytest.mark.parametrize("offset", ["0", "-5", "abc"])
def test_events_endpoint_rejects_invalid_offset(client, offset):
    response = client.get("/stats/events", params={"offset": offset})
    assert response.status_code == 422


def test_events_endpoint_requires_offset(client):
    assert client.get("/stats/events").status_code == 422


def test_pull_request_endpoint(client):
    response = client.get("/stats/pull-requests/average-time", params={"repo": "x/y"})
    assert response.status_code == 200
    assert response.json() == {
        "repo": "x/y",
        "action": "all",
        "pull_request_events": 0,
        "avg_seconds": None,
    }


def test_pull_request_endpoint_accepts_action_filter(client):
    params = {"repo": "x/y", "action": "opened"}
    response = client.get("/stats/pull-requests/average-time", params=params)
    assert response.status_code == 200
    assert response.json()["action"] == "opened"


def test_pull_request_endpoint_rejects_unknown_action(client):
    params = {"repo": "x/y", "action": "merged"}  # bestaat niet: is 'closed'
    response = client.get("/stats/pull-requests/average-time", params=params)
    assert response.status_code == 422


def test_chart_endpoint_returns_png(client):
    response = client.get("/stats/events/chart", params={"offset": 30})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")  # de 'handtekening' van elk PNG-bestand
