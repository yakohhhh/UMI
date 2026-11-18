from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from umi_api.api.deps import get_database
from umi_api.db.session import Database
from umi_api.schemas.health import Health

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=Health)
async def healthz() -> Health:
    """The process is up."""
    return Health(status="ok")


@router.get("/readyz", response_model=Health, responses={503: {"description": "The database is unreachable"}})
async def readyz(database: Annotated[Database, Depends(get_database)]) -> Health:
    """The database answers."""
    try:
        await database.ping()
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unreachable") from exc
    return Health(status="ready")
