"""Tests voor het inlezen van de configuratie."""

from github_monitor.config import load_settings


def test_github_repos_is_parsed_from_comma_separated_list(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOS", "fastapi/fastapi, microsoft/vscode ,")
    assert load_settings().github_repos == ["fastapi/fastapi", "microsoft/vscode"]


def test_github_repos_is_empty_by_default(monkeypatch):
    monkeypatch.delenv("GITHUB_REPOS", raising=False)
    assert load_settings().github_repos == []
