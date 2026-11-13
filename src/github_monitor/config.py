"""Configuratie via omgevingsvariabelen. Alles heeft een standaardwaarde."""

import os
from dataclasses import dataclass
from typing import Literal

# De drie eventtypes uit de opdracht. Alle andere types gooit de transform-stap weg.
EVENT_TYPES = ("WatchEvent", "PullRequestEvent", "IssuesEvent")

# Mogelijke waarden van payload.action bij een PullRequestEvent (bron: GitHub-docs).
# "merged" bestaat niet als action: dat is "closed" met pull_request.merged = true.
# Als Literal-type: FastAPI toont ze als keuzelijst in /docs en weigert andere waarden (422).
PullRequestAction = Literal[
    "opened",
    "closed",
    "reopened",
    "edited",
    "synchronize",
    "assigned",
    "unassigned",
    "labeled",
    "unlabeled",
    "review_requested",
    "review_request_removed",
]


@dataclass
class Settings:
    github_token: str | None  # optioneel: zonder token 60 requests/uur, met token 5000
    db_path: str  # waar het SQLite-bestand staat
    collector_enabled: bool  # uitzetten in tests, zodat we GitHub niet echt aanroepen
    github_repos: list[str]  # repo's die we extra pollen, bv. ["fastapi/fastapi"]


def load_settings() -> Settings:
    # GITHUB_REPOS="owner/repo,owner/repo2" -> ["owner/repo", "owner/repo2"]
    repos = [repo.strip() for repo in os.getenv("GITHUB_REPOS", "").split(",") if repo.strip()]
    return Settings(
        github_token=os.getenv("GITHUB_TOKEN") or None,
        db_path=os.getenv("DB_PATH", "data/events.db"),
        collector_enabled=os.getenv("COLLECTOR_ENABLED", "true").lower() == "true",
        github_repos=repos,
    )
