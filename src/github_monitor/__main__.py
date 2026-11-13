"""Startpunt: `uv run github-monitor` start de API (en daarmee de collector)."""

import uvicorn


def main() -> None:
    # Eén worker: met meer workers zou de collector meerdere keren draaien.
    uvicorn.run("github_monitor.api:app", host="127.0.0.1", port=8000, workers=1)


if __name__ == "__main__":
    main()
