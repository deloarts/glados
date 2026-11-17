"""Administrative removal of one user's time tracking credentials, the step
before turning that user into a shared or service account, which is refused
while credentials are stored. Needs write:settings for anyone but oneself,
and never reveals the stored values. A no-op when nothing is stored."""

from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteUserTimeTrackingCredentials:
    def __init__(
        self,
        user_repo: IUserRepository,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._users = user_repo
        self._credentials = credentials_repo
        self._uow = uow

    async def execute(self, actor: User, target_id: int) -> None:
        UserRules.assert_can_delete_time_tracking_credentials(actor, target_id)
        target = found_or_raise(
            await self._users.get_by_id(target_id),
            UserNotFoundError,
            f"User #{target_id} not found.",
        )

        removed = await self._credentials.delete_for_user(target.id)
        await self._uow.commit()
        if removed:
            log.info(
                f"Removed the time tracking credentials of {target.username!r} (ID={target.id})."
            )
