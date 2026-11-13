"""De REST API (FastAPI). Start bij het opstarten ook de collector op de achtergrond."""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Query, Response

from github_monitor import stats
from github_monitor.chart import render_events_chart
from github_monitor.collector import run_collector
from github_monitor.config import PullRequestAction, Settings, load_settings
from github_monitor.db import connect
from github_monitor.etl import utc_now

# De offset-parameter, gedeeld door twee endpoints: verplicht, hele minuten, minimaal 1.
OffsetParam = Annotated[int, Query(ge=1, description="Aantal minuten terugkijken, bv. 10")]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Bij opstarten: database openen en de collector als achtergrondtaak starten.
        app.state.conn = connect(settings.db_path)
        task = None
        if settings.collector_enabled:
            task = asyncio.create_task(
                run_collector(app.state.conn, settings.github_token, settings.github_repos)
            )
        yield
        # Bij afsluiten: collector netjes stoppen en database sluiten.
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        app.state.conn.close()

    app = FastAPI(
        title="GitHub Monitor",
        description="Statistieken over WatchEvent, PullRequestEvent en IssuesEvent op GitHub.",
        lifespan=lifespan,
    )

    # Annotated[type, Query(...)]: het type zegt wat voor waarde het is, Query(...) voegt
    # validatie en uitleg voor /docs toe. FastAPI controleert de invoer automatisch (422).

    @app.get("/stats/events")
    async def events_by_type(offset: OffsetParam) -> dict:
        """Aantal events per type dat in de laatste `offset` minuten is aangemaakt."""
        return stats.count_events_by_type(app.state.conn, offset, now=utc_now())

    @app.get("/stats/pull-requests/average-time")
    async def average_pull_request_time(
        repo: Annotated[
            str, Query(description="Repository als 'owner/repo'", examples=["home-assistant/core"])
        ],
        action: Annotated[
            PullRequestAction | None,
            Query(description="Optioneel: alleen deze action tellen, bv. 'opened'"),
        ] = None,
    ) -> dict:
        """Gemiddelde tijd (seconden) tussen PullRequestEvents voor één repository."""
        return stats.average_time_between_pull_requests(app.state.conn, repo, action)

    @app.get(
        "/stats/events/chart",
        response_class=Response,
        responses={200: {"content": {"image/png": {}}}},
    )
    async def events_chart(offset: OffsetParam) -> Response:
        """Bonus: grafiek (PNG) van het aantal events per minuut per type."""
        data = stats.events_per_minute(app.state.conn, offset, now=utc_now())
        png = render_events_chart(data, offset)
        return Response(content=png, media_type="image/png")

    return app


app = create_app()
