"""Use-case factories for the API-key surface's PDM endpoints
(v1/key/endpoints/pdm.py), the PAT surface's pre-release validation and
trigger batch endpoints (v1/pat/endpoints/pdm.py), and the web
catalogue's read-only preview endpoint (v1/web/endpoints/pdm.py).
RequestPdmFileRefresh only stages an event and commits, it never talks
to the PDM Web API itself (that happens later, in the pdm_sync worker
wired in main.py), so it needs the transactional event bus/unit of work
and the shared in-process trigger rate limiter, not a gateway factory. ValidatePdmFile,
GetPdmTriggerConfig and ValidatePdmPayload are the opposite: read-only, no
event bus or unit of work at all, ValidatePdmFile and GetPdmTriggerConfig
additionally need the PDM session service to resolve data fresh from the
vault. ValidatePdmPayload (reused as-is by the PAT endpoint) needs the
snapshot repository instead, to resolve a PAT caller's own file identity
from its document path rather than a vault round trip, see
application.services.pdm_field_resolution.resolve_file_identity_from_path.
ListPdmPreview is likewise read-only, over the snapshot table plus the
made/bought repositories rather than the vault.
"""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_article_group_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_customer_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import (
    get_part_number_registry_repo,
)
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IPartNumberRegistryCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_external_data_settings_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_pdm_file_snapshot_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.repositories import get_pdm_sync_run_repo
from src.modules.external_data.adapters.inbound.api.deps.services import (
    get_pdm_trigger_rate_limiter,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import get_pdm_session_service
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_trigger_rate_limiter import (
    PdmTriggerRateLimiter,
)
from src.modules.external_data.application.use_cases.pdm.get_pdm_trigger_config import (
    GetPdmTriggerConfig,
)
from src.modules.external_data.application.use_cases.pdm.list_pdm_file_history import (
    ListPdmFileHistory,
)
from src.modules.external_data.application.use_cases.pdm.list_pdm_preview import ListPdmPreview
from src.modules.external_data.application.use_cases.pdm.request_pdm_file_refresh import (
    RequestPdmFileRefresh,
)
from src.modules.external_data.application.use_cases.pdm.validate_pdm_file import ValidatePdmFile
from src.modules.external_data.application.use_cases.pdm.validate_pdm_payload import (
    ValidatePdmPayload,
)
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_request_pdm_file_refresh_use_case(
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    rate_limiter: PdmTriggerRateLimiter = Depends(get_pdm_trigger_rate_limiter),
) -> RequestPdmFileRefresh:
    return RequestPdmFileRefresh(
        admin_settings_repo=admin_settings_repo,
        event_bus=event_bus,
        uow=uow,
        rate_limiter=rate_limiter,
    )


def get_validate_pdm_payload_use_case(
    made_item_repo: IMadeItemCadStore = Depends(get_made_item_repo),
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    article_group_repo: IArticleGroupQueries = Depends(get_article_group_repo),
    source_item_repo: ISourceItemQueries = Depends(get_source_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    part_number_registry: IPartNumberRegistryCadStore = Depends(get_part_number_registry_repo),
    pdm_file_snapshot_repo: IPdmFileSnapshotRepository = Depends(get_pdm_file_snapshot_repo),
    customer_repo: ICustomerQueries = Depends(get_customer_repo),
) -> ValidatePdmPayload:
    return ValidatePdmPayload(
        made_item_repo=made_item_repo,
        bought_item_repo=bought_item_repo,
        article_group_repo=article_group_repo,
        source_item_repo=source_item_repo,
        supplier_repo=supplier_repo,
        admin_settings_repo=admin_settings_repo,
        part_number_registry=part_number_registry,
        pdm_file_snapshot_repo=pdm_file_snapshot_repo,
        customer_repo=customer_repo,
    )


def get_validate_pdm_file_use_case(
    session: PdmSessionService = Depends(get_pdm_session_service),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    validate: ValidatePdmPayload = Depends(get_validate_pdm_payload_use_case),
) -> ValidatePdmFile:
    return ValidatePdmFile(
        session=session, admin_settings_repo=admin_settings_repo, validate=validate
    )


def get_pdm_trigger_config_use_case(
    session: PdmSessionService = Depends(get_pdm_session_service),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
) -> GetPdmTriggerConfig:
    return GetPdmTriggerConfig(session=session, admin_settings_repo=admin_settings_repo)


def get_list_pdm_file_history_use_case(
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    run_repo: IPdmSyncRunRepository = Depends(get_pdm_sync_run_repo),
) -> ListPdmFileHistory:
    return ListPdmFileHistory(admin_settings_repo=admin_settings_repo, run_repo=run_repo)


def get_list_pdm_preview_use_case(
    snapshot_repo: IPdmFileSnapshotRepository = Depends(get_pdm_file_snapshot_repo),
    made_item_repo: IMadeItemCadStore = Depends(get_made_item_repo),
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
) -> ListPdmPreview:
    return ListPdmPreview(
        snapshot_repo=snapshot_repo,
        made_item_repo=made_item_repo,
        bought_item_repo=bought_item_repo,
        admin_settings_repo=admin_settings_repo,
    )
