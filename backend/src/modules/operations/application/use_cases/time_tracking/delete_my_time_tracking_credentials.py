"""Removes the actor's own time tracking credentials together with the
consent stored on them, which is how a user withdraws. Works whether or not
the integration is currently enabled, because withdrawing must always be
possible, and is a no-op when nothing is stored."""

from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteMyTimeTrackingCredentials:
    def __init__(
        self,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._credentials = credentials_repo
        self._uow = uow

    async def execute(self, actor: User) -> None:
        removed = await self._credentials.delete_for_user(actor.id)
        await self._uow.commit()
        if removed:
            log.info("Time tracking credentials removed.")
