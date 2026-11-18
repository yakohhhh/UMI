"""`umi-api`: run, migrate and seed the backend."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from umi_api.clock import SystemClock
from umi_api.db import migrate as migrations
from umi_api.db.session import Database
from umi_api.domain.aggregation import MIN_RIDERS
from umi_api.main import create_app
from umi_api.seed import SeedReport, load_mock_data, seed_demo
from umi_api.services.aggregation import AggregationReport, AggregationService
from umi_api.settings import get_settings

app = typer.Typer(help="UMI backend: REST API, database migrations and demo data.", no_args_is_help=True)


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Interface to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on.")] = 8000,
    reload: Annotated[bool, typer.Option(help="Restart on code changes (development).")] = False,
) -> None:
    """Serve the /v1 API."""
    uvicorn.run("umi_api.main:create_app", factory=True, host=host, port=port, reload=reload)


@app.command()
def migrate(revision: Annotated[str, typer.Argument(help="Target revision.")] = "head") -> None:
    """Apply database migrations (UMI_DATABASE_URL)."""
    migrations.upgrade(get_settings().database_url, revision)
    typer.echo(f"Database at {revision}.")


@app.command()
def seed(
    data_dir: Annotated[
        Path | None, typer.Option(help="Mock datasets to load (default: UMI_MOCK_DATA_DIR).", file_okay=False)
    ] = None,
) -> None:
    """Load the web app's mock datasets, dates shifted to this week. Safe to run again."""
    settings = get_settings()
    report = asyncio.run(_seed(settings.database_url, data_dir or settings.mock_data_dir))
    typer.echo(
        f"Seeded {report.activities} activities, {report.hazards} hazards and {report.hotspot_answers} "
        f"hotspot answers; dates moved {report.week_shift_days} days (demo now: {report.as_of:%Y-%m-%d %H:%M} UTC)."
    )


@app.command()
def aggregate() -> None:
    """Recompute every street's hourly scores from riders' passes of the last 30 days and the seeded baseline."""
    report = asyncio.run(_aggregate(get_settings().database_url))
    typer.echo(
        f"Published {report.segments} segments: {report.from_riders} segment-hours include riders' passes, "
        f"{report.held_back} kept their baseline (fewer than {MIN_RIDERS} distinct riders)."
    )


@app.command()
def openapi(
    output: Annotated[Path | None, typer.Option(help="Write to a file instead of stdout.", dir_okay=False)] = None,
) -> None:
    """Print the OpenAPI document."""
    document = json.dumps(create_app().openapi(), indent=2, ensure_ascii=False)
    if output is None:
        typer.echo(document)
    else:
        output.write_text(document + "\n", encoding="utf-8")


async def _seed(database_url: str, data_dir: Path) -> SeedReport:
    data = load_mock_data(data_dir)
    database = Database(database_url)
    try:
        async with database.sessions() as session:
            return await seed_demo(session, data, SystemClock().now())
    finally:
        await database.dispose()


async def _aggregate(database_url: str) -> AggregationReport:
    database = Database(database_url)
    try:
        async with database.sessions() as session:
            report = await AggregationService(session, SystemClock()).run()
            await session.commit()
            return report
    finally:
        await database.dispose()
