"""Use case factory: deleting the time tracking credentials a user saved."""

from fastapi import Depends

from src.modules.operations.adapters.inbound.api.deps.repositories import (
    get_user_time_tracking_credentials_repo,
)
from src.modules.operations.application.use_cases.time_tracking.delete_user_time_tracking_credentials import (
    DeleteUserTimeTrackingCredentials,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_delete_user_time_tracking_credentials_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    credentials_repo: IUserTimeTrackingCredentialsRepository = Depends(
        get_user_time_tracking_credentials_repo
    ),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteUserTimeTrackingCredentials:
    return DeleteUserTimeTrackingCredentials(user_repo, credentials_repo, uow=uow)
