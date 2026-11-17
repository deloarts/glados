"""Converts between MachineDowntime domain entities and DTOs."""

from src.modules.fulfillment.application.dto.machine_downtime_dto import MachineDowntimeResult
from src.modules.fulfillment.application.dto.machine_downtime_dto import OpenMachineDowntimeResult
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime


class MachineDowntimeMapper:
    @staticmethod
    def to_result(entity: MachineDowntime) -> MachineDowntimeResult:
        return MachineDowntimeResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            machine_id=entity.machine_id,
            machine_internal_name=entity.machine_internal_name,
            started_at=entity.started_at,
            ended_at=entity.ended_at,
            reason=entity.reason,
            note=entity.note,
            reported_by_id=entity.reported_by_id,
            reported_by_full_name=entity.reported_by_full_name,
            ended_by_id=entity.ended_by_id,
            ended_by_full_name=entity.ended_by_full_name,
            changed_by_id=entity.changed_by_id,
            changed_by_full_name=entity.changed_by_full_name,
            changes=entity.changes,
        )

    @staticmethod
    def to_open_result(entity: MachineDowntime) -> OpenMachineDowntimeResult:
        return OpenMachineDowntimeResult(
            id=entity.id, started_at=entity.started_at, reason=entity.reason
        )
