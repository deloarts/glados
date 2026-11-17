"""Repository factories on the request's session, and the module's settings
store."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_demand_bucket_repository import (
    SqlAlchemyBoughtItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.fulfillment_settings_repository import (
    SqlAlchemyFulfillmentSettingsRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_calendar_repository import (
    SqlAlchemyMachineCalendarRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_downtime_repository import (
    SqlAlchemyMachineDowntimeRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_bucket_repository import (
    SqlAlchemyMadeItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.manufacturing_assessment_repository import (
    SqlAlchemyManufacturingAssessmentRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_file_repository import (
    SqlAlchemyOrderFileRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderItemDeliveryRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_file_repository import (
    SqlAlchemyProductionOrderFileRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_file_repository import (
    SqlAlchemyQuoteRequestFileRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_file_repository import (
    SqlAlchemyQuoteRequestSupplierRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository import (
    SqlAlchemyQuoteRequestRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_bucket_repository import (
    SqlAlchemySourceItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_bucket_repository import (
    IBoughtItemDemandBucketRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    IMachineDowntimeRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_bucket_repository import (
    IMadeItemDemandBucketRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.manufacturing_assessment_repository import (
    IManufacturingAssessmentRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_file_repository import (
    IOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_file_repository import (
    IQuoteRequestFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_file_repository import (
    IQuoteRequestSupplierRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    IQuoteRequestRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_bucket_repository import (
    ISourceItemDemandBucketRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import repo_factory

get_source_item_demand_repo: Callable[[AsyncSession], ISourceItemDemandRepository] = repo_factory(
    SqlAlchemySourceItemDemandRepository
)
get_source_item_demand_bucket_repo: Callable[[AsyncSession], ISourceItemDemandBucketRepository] = (
    repo_factory(SqlAlchemySourceItemDemandBucketRepository)
)
get_source_item_allocation_repo: Callable[[AsyncSession], ISourceItemAllocationRepository] = (
    repo_factory(SqlAlchemySourceItemAllocationRepository)
)
get_demand_item_repo: Callable[[AsyncSession], IBoughtItemDemandItemRepository] = repo_factory(
    SqlAlchemyBoughtItemDemandItemRepository
)
get_bought_item_demand_bucket_repo: Callable[[AsyncSession], IBoughtItemDemandBucketRepository] = (
    repo_factory(SqlAlchemyBoughtItemDemandBucketRepository)
)
get_order_repo: Callable[[AsyncSession], IOrderRepository] = repo_factory(SqlAlchemyOrderRepository)
get_quote_request_repo: Callable[[AsyncSession], IQuoteRequestRepository] = repo_factory(
    SqlAlchemyQuoteRequestRepository
)
get_quote_request_file_repo: Callable[[AsyncSession], IQuoteRequestFileRepository] = repo_factory(
    SqlAlchemyQuoteRequestFileRepository
)
get_quote_request_supplier_repo: Callable[[AsyncSession], IQuoteRequestSupplierRepository] = (
    repo_factory(SqlAlchemyQuoteRequestSupplierRepository)
)
get_made_item_demand_repo: Callable[[AsyncSession], IMadeItemDemandItemRepository] = repo_factory(
    SqlAlchemyMadeItemDemandItemRepository
)
get_made_item_demand_bucket_repo: Callable[[AsyncSession], IMadeItemDemandBucketRepository] = (
    repo_factory(SqlAlchemyMadeItemDemandBucketRepository)
)
get_made_item_allocation_repo: Callable[[AsyncSession], IMadeItemAllocationRepository] = (
    repo_factory(SqlAlchemyMadeItemAllocationRepository)
)
get_production_lot_repo: Callable[[AsyncSession], IProductionLotRepository] = repo_factory(
    SqlAlchemyProductionLotRepository
)
get_production_machine_repo: Callable[[AsyncSession], IProductionMachineRepository] = repo_factory(
    SqlAlchemyProductionMachineRepository
)
get_machine_pool_repo: Callable[[AsyncSession], IMachinePoolRepository] = repo_factory(
    SqlAlchemyMachinePoolRepository
)
get_machine_calendar_repo: Callable[[AsyncSession], IMachineCalendarRepository] = repo_factory(
    SqlAlchemyMachineCalendarRepository
)
get_machine_downtime_repo: Callable[[AsyncSession], IMachineDowntimeRepository] = repo_factory(
    SqlAlchemyMachineDowntimeRepository
)
get_production_order_repo: Callable[[AsyncSession], IProductionOrderRepository] = repo_factory(
    SqlAlchemyProductionOrderRepository
)
get_production_order_interruption_repo: Callable[
    [AsyncSession], IProductionOrderInterruptionRepository
] = repo_factory(SqlAlchemyProductionOrderInterruptionRepository)


get_production_order_file_repo: Callable[[AsyncSession], IProductionOrderFileRepository] = (
    repo_factory(SqlAlchemyProductionOrderFileRepository)
)
get_manufacturing_assessment_repo: Callable[[AsyncSession], IManufacturingAssessmentRepository] = (
    repo_factory(SqlAlchemyManufacturingAssessmentRepository)
)
get_order_file_repo: Callable[[AsyncSession], IOrderFileRepository] = repo_factory(
    SqlAlchemyOrderFileRepository
)
get_order_item_repo: Callable[[AsyncSession], IOrderItemRepository] = repo_factory(
    SqlAlchemyOrderItemRepository
)
get_allocation_repo: Callable[[AsyncSession], IBoughtItemAllocationRepository] = repo_factory(
    SqlAlchemyBoughtItemAllocationRepository
)
get_order_item_delivery_repo: Callable[[AsyncSession], IOrderItemDeliveryRepository] = repo_factory(
    SqlAlchemyOrderItemDeliveryRepository
)

get_fulfillment_settings_repo: Callable[[AsyncSession], IFulfillmentSettingsRepository] = (
    repo_factory(SqlAlchemyFulfillmentSettingsRepository)
)
