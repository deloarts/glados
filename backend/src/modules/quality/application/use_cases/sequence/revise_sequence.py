"""
Starts a new revision of a released sequence. The new revision is a draft
with the steps of the released one and the next revision string in the
scheme of the admin settings. The released revision is no longer the
latest one and stays the valid record until the new revision is released.
"""

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.sequence_dto import ReviseSequenceCommand
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import SequenceSummaryResult
from src.modules.quality.application.use_cases._controlled_documents.base import (
    ReviseControlledDocument,
)
from src.modules.quality.application.use_cases.sequence._kind import KIND
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository


class ReviseSequence(ReviseControlledDocument[Sequence, SequenceResult, SequenceSummaryResult]):
    _kind = KIND

    def __init__(
        self,
        sequence_repo: ISequenceRepository,
        admin_settings_repo: IFulfillmentSettingsRepository,
        event_bus: IEventBus,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(sequence_repo, admin_settings_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, sequence_id: int, cmd: ReviseSequenceCommand
    ) -> SequenceResult:
        return await self._revise(actor, sequence_id, cmd.reason)
