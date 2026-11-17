"""
Releases a calculation (the sign-off that makes it read-only for good) and
marks a released revision invalid. The author may release their own
calculation. Releasing a later revision supersedes the one before it. A
release is never taken back: a revision found to be wrong is marked
invalid with a reason, which needs manage:calculations and tells everyone who
worked on the document, and corrected by a new revision. Releasing freezes
the name of the referenced device into the revision.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CalculationSummaryResult
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.use_cases._controlled_documents.base import (
    MarkControlledDocumentInvalid,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    ReleaseControlledDocument,
)
from src.modules.quality.application.use_cases.calculation._kind import KIND
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)


class ReleaseCalculation(
    ReleaseControlledDocument[Calculation, CalculationResult, CalculationSummaryResult]
):
    """Before the shared release runs, the referenced device's current name
    is frozen onto the revision, in the same unit of work, so the released
    document keeps naming the device as it was named then."""

    _kind = KIND

    def __init__(self, calculation_repo: ICalculationRepository, *, uow: IUnitOfWork) -> None:
        super().__init__(calculation_repo, uow=uow)
        self._calculations = calculation_repo

    async def execute(self, actor: User, calculation_id: int) -> CalculationResult:
        KIND.rules.assert_can_release_any(actor)
        calculation = await self._load(calculation_id)
        KIND.rules.assert_can_release(actor, calculation)
        if calculation.product_device_name != calculation.product_device_current_name:
            calculation.product_device_name = calculation.product_device_current_name
            await self._calculations.save(calculation)
        return await self._release(actor, calculation_id)


class MarkCalculationInvalid(
    MarkControlledDocumentInvalid[Calculation, CalculationResult, CalculationSummaryResult]
):
    _kind = KIND

    def __init__(
        self, calculation_repo: ICalculationRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(calculation_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, calculation_id: int, cmd: MarkInvalidCommand
    ) -> CalculationResult:
        return await self._mark_invalid(actor, calculation_id, cmd)
