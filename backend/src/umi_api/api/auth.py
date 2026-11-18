"""Who is calling. Development tokens only, until real rider accounts exist.

`Authorization: Bearer dev:<athleteId>` acts as that rider; without the header,
UMI_DEV_DEFAULT_ATHLETE is used. Production refuses both. Everything that
depends on the caller goes through `CurrentAthlete`, so swapping this module
for real authentication changes nothing else.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from umi_api.api.deps import SessionDep, SettingsDep
from umi_api.repositories.athletes import AthleteRepository

DEV_TOKEN_PREFIX = "dev:"

_bearer = HTTPBearer(auto_error=False, description="Development: `dev:<athleteId>`")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


async def current_athlete_id(
    settings: SettingsDep,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if settings.is_production:
        raise _unauthorized("Rider accounts are not available yet")
    if credentials is None:
        athlete_id = settings.dev_default_athlete
    elif credentials.credentials.startswith(DEV_TOKEN_PREFIX):
        athlete_id = credentials.credentials.removeprefix(DEV_TOKEN_PREFIX)
    else:
        raise _unauthorized("Unsupported token: use `dev:<athleteId>` in development")
    if await AthleteRepository(session).get(athlete_id) is None:
        raise _unauthorized(f"Unknown rider {athlete_id!r}")
    return athlete_id


def dev_token(athlete_id: str) -> str:
    """The development bearer token that acts as `athlete_id`."""
    return f"{DEV_TOKEN_PREFIX}{athlete_id}"


def current_city_account(settings: SettingsDep) -> str:
    """The City Insights account calling (an organisation, not a rider)."""
    if settings.is_production:
        raise _unauthorized("City accounts are not available yet")
    return settings.dev_default_city_account


CurrentAthlete = Annotated[str, Depends(current_athlete_id)]
CurrentCityAccount = Annotated[str, Depends(current_city_account)]
