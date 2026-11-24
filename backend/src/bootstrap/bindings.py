"""
Binds the request dependencies a module declares but cannot build, because
their implementations live in a module above it, in the read tier or here
(platform `deps/binding.py`). `register_all` calls `bind_request_dependencies`
once per process, before the first request.

Each binding is a builder on the request's session. Most are a repository or
an adapter of the module that implements the port; the rest compose a read
tier service or the service health checker from the repositories of several
modules, which only the composition root may do.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.external.system.service_health_checker import (
    ServiceHealthChecker,
)
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.inbound.api.deps import bindings as catalogue
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_item_picture_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_file_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.external_data.adapters.outbound.external.pdm.factory import create_pdm_gateway
from src.modules.external_data.adapters.outbound.external.stock_service.factory import (
    create_stock_service,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.external_data_settings_repository import (
    SqlAlchemyExternalDataSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_document_link_repository import (
    SqlAlchemyPdmDocumentLinkRepository,
)
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.external_data.application.services.stock_service import (
    service_connection as stock_service_connection,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    build_requested_schedule_walk,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_scheduling_repos
from src.modules.fulfillment.adapters.inbound.api.deps.projects import (
    build_project_work_propagation,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_calendar_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_downtime_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_pool_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_made_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_made_item_demand_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_order_item_delivery_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_machine_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_order_interruption_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.services import (
    build_schedule_recompute_generation_counter,
)
from src.modules.fulfillment.adapters.inbound.api.deps.services import get_bought_item_usages
from src.modules.fulfillment.adapters.inbound.api.deps.services import get_made_item_usages
from src.modules.fulfillment.adapters.inbound.api.deps.services import get_project_work
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_calendar_repository import (
    SqlAlchemyMachineCalendarRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.application.facade.external_work import GetExternalWork
from src.modules.operations.adapters.inbound.api.deps import bindings as operations
from src.modules.operations.adapters.outbound.external.time_tracking_service.factory import (
    create_time_tracking_provider,
)
from src.modules.operations.adapters.outbound.external.weather.service import get_weather_service
from src.modules.operations.adapters.outbound.persistence.repositories.time_tracking_credentials_repository import (
    SqlAlchemyUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.application.services.time_tracking_service import service_connection
from src.modules.platform.adapters.inbound.api.deps import bindings as platform
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.ports.outbound.service_health_port import IServiceHealthChecker
from src.modules.quality.adapters.inbound.api.deps import bindings as quality
from src.modules.quality.adapters.inbound.api.deps.meeting_notes_journal import (
    build_meeting_notes_journal,
)
from src.modules.quality.adapters.inbound.api.deps.product_documents import build_product_documents
from src.modules.quality.adapters.inbound.api.deps.repositories import get_production_kpi_repo
from src.modules.workspace.adapters.inbound.api.deps import bindings as workspace
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_snapshot_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.application.services.meeting_contact_copies import MeetingContactCopies
from src.read.adapters.inbound.api import deps as read
from src.read.application.services.print_root_resolver import PrintRootResolver
from src.read.application.use_cases.infoscreen.build_infoscreen_feed import BuildInfoscreenFeed


def bind_request_dependencies() -> None:
    """Binds every module's request bindings to their implementations."""
    platform.tenant_holidays.bind(SqlAlchemyMachineCalendarRepository)
    platform.schedule_generation_counter.bind(build_schedule_recompute_generation_counter)
    platform.schedule_recompute.bind(build_requested_schedule_walk)
    platform.service_health_checker.bind(build_service_health_checker)
    platform.user_held_credentials.bind(SqlAlchemyUserTimeTrackingCredentialsRepository)
    platform.linked_files.bind(SqlAlchemyPdmDocumentLinkRepository)
    catalogue.cad_source.bind(build_cad_source)
    catalogue.bought_item_usages.bind(get_bought_item_usages)
    catalogue.made_item_usages.bind(get_made_item_usages)
    catalogue.default_machine_lookup.bind(SqlAlchemyProductionMachineRepository)
    catalogue.inspection_method_usage.bind(get_fulfillment_settings_repo)
    catalogue.contact_copies.bind(build_contact_copies)
    workspace.project_work.bind(get_project_work)
    workspace.product_work.bind(SqlAlchemyOrderRepository)
    workspace.project_work_propagation.bind(build_project_work_propagation)
    workspace.product_documents.bind(build_product_documents)
    workspace.meeting_notes_journal.bind(build_meeting_notes_journal)
    quality.print_root_resolver.bind(build_print_root_resolver)
    operations.infoscreen_feed_builder.bind(build_infoscreen_feed)
    read.admin_settings.bind(SqlAlchemyAdminSettingsRepository)


def build_contact_copies(db: AsyncSession) -> MeetingContactCopies:
    """Workspace blanks the copies of an anonymised contact that its meetings
    and the snapshots of their notes keep, and its address among the
    recipients of sent notes in the export journal."""
    return MeetingContactCopies(
        get_meeting_repo(db), get_meeting_snapshot_repo(db), build_meeting_notes_journal(db)
    )


def build_cad_source(db: AsyncSession) -> PdmCadSource:
    """CAD & external data answers Catalogue's CAD source port from the PDM
    settings."""
    return PdmCadSource(SqlAlchemyExternalDataSettingsRepository(db))


async def build_service_health_checker(db: AsyncSession) -> IServiceHealthChecker:
    """The health checker of the services Glados depends on, with a PDM, a
    time tracking and a stock service client only when each is on and
    configured."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    pdm_settings = await repo.get_pdm()
    pdm = (
        create_pdm_gateway(
            PdmConnection(
                base_url=pdm_settings.base_url,
                vault_name=pdm_settings.vault_name,
                verify_certificate=pdm_settings.verify_certificate,
                timeout_seconds=pdm_settings.timeout_seconds,
            )
        )
        if pdm_settings.enabled and pdm_settings.is_configured
        else None
    )
    time_tracking_settings = await repo.get_time_tracking()
    time_tracking = (
        create_time_tracking_provider(service_connection(time_tracking_settings))
        if time_tracking_settings.enabled and time_tracking_settings.is_configured
        else None
    )
    stock_settings = await repo.get_stock()
    stock = (
        create_stock_service(stock_service_connection(stock_settings))
        if stock_settings.is_ready
        else None
    )
    return ServiceHealthChecker(
        db=db,
        redis_client=get_async_redis_client(),
        storage=await get_optional_storage_adapter(db),
        storage_settings=await repo.get_storage(),
        pdm=pdm,
        time_tracking=time_tracking,
        stock=stock,
    )


def build_print_root_resolver(db: AsyncSession) -> PrintRootResolver:
    """The read tier's print root resolver on the repositories of every
    module whose rows a print template may start from."""
    return PrintRootResolver(
        order_repo=get_order_repo(db),
        order_item_repo=get_order_item_repo(db),
        production_order_repo=get_production_order_repo(db),
        production_lot_repo=get_production_lot_repo(db),
        made_item_repo=get_made_item_repo(db),
        bought_item_repo=get_bought_item_repo(db),
        source_item_repo=get_source_item_repo(db),
        order_item_delivery_repo=get_order_item_delivery_repo(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
    )


def build_infoscreen_feed(db: AsyncSession) -> BuildInfoscreenFeed:
    """The read tier's infoscreen feed on the scheduling, KPI and picture
    repositories it reads."""
    settings_repo = get_fulfillment_settings_repo(db)
    return BuildInfoscreenFeed(
        repos=get_scheduling_repos(
            order_repo=get_production_order_repo(db),
            lot_repo=get_production_lot_repo(db),
            order_item_repo=get_order_item_repo(db),
            source_item_demand_repo=get_source_item_demand_repo(db),
            source_item_allocation_repo=get_source_item_allocation_repo(db),
            made_item_allocation_repo=get_made_item_allocation_repo(db),
            made_item_demand_repo=get_made_item_demand_repo(db),
            settings_repo=settings_repo,
        ),
        machine_repo=get_production_machine_repo(db),
        pool_repo=get_machine_pool_repo(db),
        downtime_repo=get_machine_downtime_repo(db),
        calendar_repo=get_machine_calendar_repo(db),
        kpi_repo=get_production_kpi_repo(db, get_production_order_interruption_repo(db)),
        order_repo=get_order_repo(db),
        order_item_repo=get_order_item_repo(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        picture_repo=get_item_picture_repo(db),
        product_repo=get_product_repo(db),
        project_repo=get_project_repo(db),
        made_item_repo=get_made_item_repo(db),
        made_item_file_repo=get_made_item_file_repo(db),
        weather=get_weather_service(),
        external_work=GetExternalWork(
            get_production_lot_repo(db),
            get_supplier_repo(db),
            settings_repo,
            get_scheduling_repos(
                order_repo=get_production_order_repo(db),
                lot_repo=get_production_lot_repo(db),
                order_item_repo=get_order_item_repo(db),
                source_item_demand_repo=get_source_item_demand_repo(db),
                source_item_allocation_repo=get_source_item_allocation_repo(db),
                made_item_allocation_repo=get_made_item_allocation_repo(db),
                made_item_demand_repo=get_made_item_demand_repo(db),
                settings_repo=settings_repo,
            ),
        ),
    )
