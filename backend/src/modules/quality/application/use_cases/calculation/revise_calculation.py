"""
Starts a new revision of a released calculation. The new revision is a
draft with the inputs and results of the released one and the next
revision string in the scheme of the admin settings. The released revision
is no longer the latest one and stays the valid record until the new
revision is released. Unlike "Save a copy", which starts an independent
calculation, a revision continues the same document.
"""

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CalculationSummaryResult
from src.modules.quality.application.dto.calculation_dto import ReviseCalculationCommand
from src.modules.quality.application.use_cases._controlled_documents.base import (
    ReviseControlledDocument,
)
from src.modules.quality.application.use_cases.calculation._kind import KIND
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)


class ReviseCalculation(
    ReviseControlledDocument[Calculation, CalculationResult, CalculationSummaryResult]
):
    _kind = KIND

    def __init__(
        self,
        calculation_repo: ICalculationRepository,
        admin_settings_repo: IFulfillmentSettingsRepository,
        event_bus: IEventBus,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(calculation_repo, admin_settings_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, calculation_id: int, cmd: ReviseCalculationCommand
    ) -> CalculationResult:
        return await self._revise(actor, calculation_id, cmd.reason)
