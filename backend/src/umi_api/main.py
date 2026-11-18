"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from umi_api.api import build_router
from umi_api.api.errors import register_error_handlers
from umi_api.clock import Clock, SystemClock
from umi_api.db.locks import CriticalSection
from umi_api.db.session import Database
from umi_api.services.street_network import StreetNetwork
from umi_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None, *, clock: Clock | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Engines connect lazily: creating it here costs nothing and works without a lifespan.
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await database.dispose()

    app = FastAPI(
        title="UMI API",
        version="1.0.0",
        summary="Street scores, rider reports and City Insights for Urban Motion Intelligence.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.clock = clock or SystemClock()
    app.state.street_network = StreetNetwork()
    app.state.ingest_section = CriticalSection("umi-ingest")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    register_error_handlers(app)
    app.include_router(build_router(settings))
    return app
