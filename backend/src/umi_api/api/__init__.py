"""HTTP layer: routers, dependencies and error mapping. No business rules here."""

from fastapi import APIRouter

from umi_api.api import account, activities, city, dev, health, ingest, riders, street_map
from umi_api.settings import Settings


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    for module in (riders, activities, street_map, city, account, ingest):
        router.include_router(module.router, prefix="/v1")
    if not settings.is_production:
        router.include_router(dev.router, prefix="/v1")
    return router
