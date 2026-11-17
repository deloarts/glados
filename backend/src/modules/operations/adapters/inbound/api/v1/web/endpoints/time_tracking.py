"""
The signed-in user's own time tracking: stored credentials (read, save,
check access, remove) and the month and year views read live through the
time tracking service. Every route works on the caller's own data only and
needs no permission beyond being signed in; shared, service and system
accounts are refused by the use cases.

Responses are marked `Cache-Control: no-store`, since they carry personal
attendance data that no browser or proxy cache should keep, and the routes
never echo request input in a validation error, since the save request
carries a password.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import Response
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_check_my_time_tracking_access_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_delete_my_time_tracking_credentials_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_my_time_tracking_credentials_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_my_time_tracking_month_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_my_time_tracking_year_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.time_tracking import (
    get_save_my_time_tracking_credentials_use_case,
)
from src.modules.operations.adapters.inbound.api.schemas.time_tracking_schema import (
    SaveTimeTrackingCredentialsRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.time_tracking_schema import (
    TimeTrackingAccountResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.time_tracking_schema import (
    TimeTrackingMonthResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.time_tracking_schema import (
    TimeTrackingYearResponse,
)
from src.modules.operations.application.dto.time_tracking_dto import (
    SaveTimeTrackingCredentialsCommand,
)
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingAccountResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingMonthResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingYearResult
from src.modules.operations.application.use_cases.time_tracking.check_my_time_tracking_access import (
    CheckMyTimeTrackingAccess,
)
from src.modules.operations.application.use_cases.time_tracking.delete_my_time_tracking_credentials import (
    DeleteMyTimeTrackingCredentials,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_credentials import (
    GetMyTimeTrackingCredentials,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_month import (
    GetMyTimeTrackingMonth,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_year import (
    GetMyTimeTrackingYear,
)
from src.modules.operations.application.use_cases.time_tracking.save_my_time_tracking_credentials import (
    SaveMyTimeTrackingCredentials,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.no_echo_route import NoInputEchoRoute
from src.modules.platform.domain.entities.user import User


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(route_class=NoInputEchoRoute, dependencies=[Depends(_no_store)])


@router.get("/me/account", response_model=TimeTrackingAccountResponse)
async def get_my_time_tracking_account(
    actor: User = Depends(get_current_active_user),
    use_case: GetMyTimeTrackingCredentials = Depends(get_my_time_tracking_credentials_use_case),
) -> TimeTrackingAccountResult:
    """The caller's stored credentials and whether they can be used. Never
    contacts the time tracking system."""
    return await use_case.execute(actor=actor)


@router.put("/me/account", response_model=TimeTrackingAccountResponse)
async def save_my_time_tracking_account(
    body: SaveTimeTrackingCredentialsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SaveMyTimeTrackingCredentials = Depends(
        get_save_my_time_tracking_credentials_use_case
    ),
) -> TimeTrackingAccountResult:
    """Seal the credentials for the time tracking service, have it verify
    them with a sign-in, and store them only when that succeeds. Returns the
    employee name and what the account may read; neither is stored."""
    cmd = SaveTimeTrackingCredentialsCommand(
        time_tracking_user=body.time_tracking_user,
        time_tracking_password=body.time_tracking_password,
        time_tracking_consent_version=body.time_tracking_consent_version,
    )
    return await use_case.execute(actor=actor, cmd=cmd)


@router.delete("/me/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_time_tracking_account(
    actor: User = Depends(get_current_active_user),
    use_case: DeleteMyTimeTrackingCredentials = Depends(
        get_delete_my_time_tracking_credentials_use_case
    ),
) -> Response:
    """Remove the caller's credentials and the consent stored with them."""
    await use_case.execute(actor=actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


@router.post("/me/account/check", response_model=TimeTrackingAccountResponse)
async def check_my_time_tracking_access(
    actor: User = Depends(get_current_active_user),
    use_case: CheckMyTimeTrackingAccess = Depends(get_check_my_time_tracking_access_use_case),
) -> TimeTrackingAccountResult:
    """Have the time tracking service sign in with the stored credentials and
    report what the account may read."""
    return await use_case.execute(actor=actor)


@router.get("/me/month", response_model=TimeTrackingMonthResponse)
async def get_my_time_tracking_month(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM"),
    actor: User = Depends(get_current_active_user),
    use_case: GetMyTimeTrackingMonth = Depends(get_my_time_tracking_month_use_case),
) -> TimeTrackingMonthResult:
    """The caller's month, read live. Future months are refused."""
    year, month_number = (int(part) for part in month.split("-"))
    return await use_case.execute(actor=actor, year=year, month=month_number)


@router.get("/me/year", response_model=TimeTrackingYearResponse)
async def get_my_time_tracking_year(
    year: int = Query(ge=2000, le=2100),
    actor: User = Depends(get_current_active_user),
    use_case: GetMyTimeTrackingYear = Depends(get_my_time_tracking_year_use_case),
) -> TimeTrackingYearResult:
    """The caller's year view, built from the months up to the current one.
    Future years are refused."""
    return await use_case.execute(actor=actor, year=year)
