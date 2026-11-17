"""
The edit lock of a calculation draft: Edit takes it, editing renews it, Discard
or leaving ends it, and it runs out by itself after a while without
activity. Taking the lock needs the same rights as changing the draft;
taking it over from another editor, or ending their editing, needs
manage:calculations, and that editor is notified.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CalculationSummaryResult
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.use_cases._controlled_documents.base import (
    LockControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    UnlockControlledDocument,
)
from src.modules.quality.application.use_cases.calculation._kind import KIND
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)


class LockCalculation(
    LockControlledDocument[Calculation, CalculationResult, CalculationSummaryResult]
):
    _kind = KIND

    def __init__(
        self, calculation_repo: ICalculationRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(calculation_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, calculation_id: int, cmd: LockCommand
    ) -> CalculationResult:
        return await self._lock(actor, calculation_id, cmd)


class UnlockCalculation(
    UnlockControlledDocument[Calculation, CalculationResult, CalculationSummaryResult]
):
    """Ends the caller's own edit lock, or with `force` someone else's, which
    needs manage:calculations; that editor is notified."""

    _kind = KIND

    def __init__(
        self, calculation_repo: ICalculationRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(calculation_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, calculation_id: int, *, force: bool = False
    ) -> CalculationResult:
        return await self._unlock(actor, calculation_id, force=force)
