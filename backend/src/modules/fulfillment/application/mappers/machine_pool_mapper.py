"""Converts between MachinePool domain entity and DTOs, including nested machine results."""

from src.modules.fulfillment.application.dto.machine_pool_dto import MachinePoolResult
from src.modules.fulfillment.application.mappers.production_machine_mapper import (
    ProductionMachineMapper,
)
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool


class MachinePoolMapper:
    @staticmethod
    def to_result(entity: MachinePool) -> MachinePoolResult:
        return MachinePoolResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            name=entity.name,
            machine_ids=entity.machine_ids,
            machines=[ProductionMachineMapper.to_result(m) for m in entity.machines],
            note=entity.note,
            creator_id=entity.creator_id,
            creator_full_name=entity.creator_full_name,
            changed_by_id=entity.changed_by_id,
            changed_by_full_name=entity.changed_by_full_name,
            changes=entity.changes,
        )
