"""Converts between ProductionMachine domain entity and DTOs, including nested fabrication
methods."""

from src.modules.catalogue.application.mappers.fabrication_method_mapper import (
    FabricationMethodMapper,
)
from src.modules.fulfillment.application.dto.machine_downtime_dto import OpenMachineDowntimeResult
from src.modules.fulfillment.application.dto.production_machine_dto import (
    ActiveProductionOrderResult,
)
from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.production_machine_status import (
    ProductionMachineStatus,
)


class ProductionMachineMapper:
    @staticmethod
    def to_result(
        entity: ProductionMachine,
        open_downtime: OpenMachineDowntimeResult | None = None,
        status: ProductionMachineStatus = ProductionMachineStatus.IDLE,
        active_orders: list[ProductionOrder] | None = None,
        live_order_count: int = 0,
    ) -> ProductionMachineResult:
        return ProductionMachineResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            internal_name=entity.internal_name,
            vendor=entity.vendor,
            model=entity.model,
            fabrication_method_ids=entity.fabrication_method_ids,
            fabrication_methods=[
                FabricationMethodMapper.to_result(m) for m in entity.fabrication_methods
            ],
            max_part_dimension=entity.max_part_dimension,
            note=entity.note,
            is_qa_machine=entity.is_qa_machine,
            creator_id=entity.creator_id,
            creator_full_name=entity.creator_full_name,
            changed_by_id=entity.changed_by_id,
            changed_by_full_name=entity.changed_by_full_name,
            changes=entity.changes,
            open_downtime=open_downtime,
            status=status.value,
            active_orders=[
                ActiveProductionOrderResult(
                    id=o.id, production_order_number=o.production_order_number, status=o.status
                )
                for o in (active_orders or [])
            ],
            live_order_count=live_order_count,
        )
