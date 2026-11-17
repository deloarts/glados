"""
Deletes the latest revision of a saved calculation for good, as long as it
is a draft; a released revision is kept as a record. Drafts go by their
creator or a manager. The revision before it, if any, becomes the latest
and valid one again.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CalculationSummaryResult
from src.modules.quality.application.use_cases._controlled_documents.base import (
    DeleteControlledDocument,
)
from src.modules.quality.application.use_cases.calculation._kind import KIND
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)


class DeleteCalculation(
    DeleteControlledDocument[Calculation, CalculationResult, CalculationSummaryResult]
):
    _kind = KIND

    def __init__(self, calculation_repo: ICalculationRepository, *, uow: IUnitOfWork) -> None:
        super().__init__(calculation_repo, uow=uow)

    async def execute(self, actor: User, calculation_id: int) -> None:
        await self._delete(actor, calculation_id)
