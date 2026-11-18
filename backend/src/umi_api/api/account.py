from fastapi import APIRouter

from umi_api.api.auth import CurrentCityAccount
from umi_api.api.deps import ClockDep, SessionDep
from umi_api.schemas.account import ApiUsage
from umi_api.services.account import AccountService

router = APIRouter(prefix="/account", tags=["city api account"])


@router.get("/usage", response_model=ApiUsage)
async def usage(account: CurrentCityAccount, session: SessionDep, clock: ClockDep) -> ApiUsage:
    """The City API key, its quota and the last 14 days of calls."""
    return await AccountService(session, clock).usage(account)
