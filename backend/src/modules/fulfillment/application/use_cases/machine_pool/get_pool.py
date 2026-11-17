"""
Retrieves one machine pool by ID, or lists machine pools with filtering and pagination.
"""

from src.modules.fulfillment.application.dto.machine_pool_dto import MachinePoolResult
from src.modules.fulfillment.application.mappers.machine_pool_mapper import MachinePoolMapper
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    MachinePoolFilterDto,
)
from src.modules.platform.application.services.lookup import found_or_raise


class PaginatedMachinePools:
    def __init__(self, total: int, items: list[MachinePoolResult]):
        self.total = total
        self.items = items


class GetMachinePool:
    def __init__(self, machine_pool_repo: IMachinePoolRepository) -> None:
        self._pools = machine_pool_repo

    async def execute(self, pool_id: int) -> MachinePoolResult:
        pool = found_or_raise(
            await self._pools.get_by_id(pool_id),
            MachinePoolNotFoundError,
            f"Machine pool #{pool_id} not found.",
        )
        return MachinePoolMapper.to_result(pool)


class GetMachinePools:
    def __init__(self, machine_pool_repo: IMachinePoolRepository) -> None:
        self._pools = machine_pool_repo

    async def execute(self, filters: MachinePoolFilterDto) -> PaginatedMachinePools:
        total, items = await self._pools.get_multi(filters)
        return PaginatedMachinePools(
            total=total, items=[MachinePoolMapper.to_result(i) for i in items]
        )
