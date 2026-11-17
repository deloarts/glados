"""Use case factories: read-only settings surfaces exposed outside the admin
settings screens (currently just the PAT field-mapping endpoint), plus the
PDM Web API session service and its use cases (settings read, admin API
console, the workflow/folder proxies, the manual poll trigger, the
pending-list read/retry/dismiss actions, the sync run log's runs/entries
reads, the PDM user matching dialog's list/link actions, and the
reconciliation report's request/read use cases). ReconcilePdmVault itself
is never built here; only the scheduler tick constructs and runs it.
"""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_external_data_settings_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_pdm_document_link_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_pdm_file_snapshot_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_pdm_reconciliation_finding_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.repositories import get_pdm_sync_run_repo
from src.modules.external_data.adapters.inbound.api.deps.services import get_pdm_catalogue
from src.modules.external_data.adapters.inbound.api.deps.services import get_pdm_gateway_factory
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.use_cases.admin_settings.browse_pdm_folders import (
    BrowsePdmFolders,
)
from src.modules.external_data.application.use_cases.admin_settings.dismiss_pdm_file import (
    DismissPdmFile,
)
from src.modules.external_data.application.use_cases.admin_settings.get_field_mapping import (
    GetFieldMapping,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_reconciliation import (
    GetPdmReconciliation,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_settings import (
    GetPdmSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_sync_activity import (
    GetPdmSyncActivity,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_workflows import (
    GetPdmWorkflows,
)
from src.modules.external_data.application.use_cases.admin_settings.invoke_pdm_operation import (
    InvokePdmOperation,
)
from src.modules.external_data.application.use_cases.admin_settings.link_pdm_users import (
    LinkPdmUsers,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_files import (
    ListPdmFiles,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_operations import (
    ListPdmOperations,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_reconciliation_findings import (
    ListPdmReconciliationFindings,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_sync_run_entries import (
    ListPdmSyncRunEntries,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_sync_runs import (
    ListPdmSyncRuns,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_users import (
    ListPdmUsers,
)
from src.modules.external_data.application.use_cases.admin_settings.request_pdm_poll import (
    RequestPdmPoll,
)
from src.modules.external_data.application.use_cases.admin_settings.request_pdm_reconciliation import (
    RequestPdmReconciliation,
)
from src.modules.external_data.application.use_cases.admin_settings.retry_pdm_file import (
    RetryPdmFile,
)
from src.modules.external_data.application.use_cases.admin_settings.update_pdm_settings import (
    UpdatePdmSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.verify_pdm_connection import (
    VerifyPdmConnection,
)
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGatewayFactory
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec
from src.modules.external_data.ports.outbound.repositories.pdm_document_link_repository import (
    IPdmDocumentLinkRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_reconciliation_finding_repository import (
    IPdmReconciliationFindingRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_pdm_link_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_field_mapping_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
) -> GetFieldMapping:
    return GetFieldMapping(repo=repo)


def get_pdm_settings_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    snapshot_repo: IPdmFileSnapshotRepository = Depends(get_pdm_file_snapshot_repo),
) -> GetPdmSettings:
    return GetPdmSettings(
        repo=repo,
        snapshot_repo=snapshot_repo,
        mutating_operations_enabled=cfg.pdm.allow_mutating_operations,
    )


def get_pdm_session_service(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    gateway_factory: IPdmGatewayFactory = Depends(get_pdm_gateway_factory),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PdmSessionService:
    return PdmSessionService(repo=repo, gateway_factory=gateway_factory, uow=uow)


def get_update_pdm_settings_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    snapshot_repo: IPdmFileSnapshotRepository = Depends(get_pdm_file_snapshot_repo),
    made_item_repo: IMadeItemCadStore | None = Depends(get_made_item_repo),
    bought_item_repo: IBoughtItemCadStore | None = Depends(get_bought_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdatePdmSettings:
    return UpdatePdmSettings(
        repo,
        snapshot_repo=snapshot_repo,
        uow=uow,
        made_item_repo=made_item_repo,
        bought_item_repo=bought_item_repo,
        mutating_operations_enabled=cfg.pdm.allow_mutating_operations,
    )


def get_verify_pdm_connection_use_case(
    gateway_factory: IPdmGatewayFactory = Depends(get_pdm_gateway_factory),
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> VerifyPdmConnection:
    return VerifyPdmConnection(gateway_factory=gateway_factory, repo=repo, uow=uow)


def get_list_pdm_operations_use_case(
    catalogue: tuple[PdmOperationSpec, ...] = Depends(get_pdm_catalogue),
) -> ListPdmOperations:
    return ListPdmOperations(catalogue=catalogue)


def get_invoke_pdm_operation_use_case(
    session: PdmSessionService = Depends(get_pdm_session_service),
    catalogue: tuple[PdmOperationSpec, ...] = Depends(get_pdm_catalogue),
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> InvokePdmOperation:
    return InvokePdmOperation(
        session=session,
        catalogue=catalogue,
        repo=repo,
        uow=uow,
        mutating_operations_enabled=cfg.pdm.allow_mutating_operations,
    )


def get_pdm_workflows_use_case(
    session: PdmSessionService = Depends(get_pdm_session_service),
) -> GetPdmWorkflows:
    return GetPdmWorkflows(session=session)


def get_browse_pdm_folders_use_case(
    session: PdmSessionService = Depends(get_pdm_session_service),
) -> BrowsePdmFolders:
    return BrowsePdmFolders(session=session)


def get_list_pdm_users_use_case(
    session: PdmSessionService = Depends(get_pdm_session_service),
    settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
) -> ListPdmUsers:
    return ListPdmUsers(
        session=session, settings_repo=settings_repo, user_repo=user_repo, link_repo=link_repo
    )


def get_link_pdm_users_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    link_repo: IUserPdmLinkRepository = Depends(get_user_pdm_link_repo),
    session: PdmSessionService = Depends(get_pdm_session_service),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> LinkPdmUsers:
    return LinkPdmUsers(user_repo=user_repo, link_repo=link_repo, session=session, uow=uow)


def get_request_pdm_poll_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RequestPdmPoll:
    return RequestPdmPoll(repo=repo, uow=uow)


def get_list_pdm_files_use_case(
    snapshot_repo: IPdmFileSnapshotRepository = Depends(get_pdm_file_snapshot_repo),
    document_link_repo: IPdmDocumentLinkRepository = Depends(get_pdm_document_link_repo),
) -> ListPdmFiles:
    return ListPdmFiles(repo=snapshot_repo, document_link_repo=document_link_repo)


def get_retry_pdm_file_use_case(
    snapshot_repo: IPdmFileSnapshotRepository = Depends(get_pdm_file_snapshot_repo),
    settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RetryPdmFile:
    return RetryPdmFile(snapshot_repo, settings_repo, event_bus=event_bus, uow=uow)


def get_dismiss_pdm_file_use_case(
    snapshot_repo: IPdmFileSnapshotRepository = Depends(get_pdm_file_snapshot_repo),
    settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    document_link_repo: IPdmDocumentLinkRepository = Depends(get_pdm_document_link_repo),
) -> DismissPdmFile:
    return DismissPdmFile(
        snapshot_repo, settings_repo, uow=uow, document_link_repo=document_link_repo
    )


def get_pdm_sync_activity_use_case(
    settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    run_repo: IPdmSyncRunRepository = Depends(get_pdm_sync_run_repo),
) -> GetPdmSyncActivity:
    return GetPdmSyncActivity(settings_repo, run_repo)


def get_list_pdm_sync_runs_use_case(
    run_repo: IPdmSyncRunRepository = Depends(get_pdm_sync_run_repo),
) -> ListPdmSyncRuns:
    return ListPdmSyncRuns(repo=run_repo)


def get_list_pdm_sync_run_entries_use_case(
    run_repo: IPdmSyncRunRepository = Depends(get_pdm_sync_run_repo),
) -> ListPdmSyncRunEntries:
    return ListPdmSyncRunEntries(repo=run_repo)


def get_request_pdm_reconciliation_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RequestPdmReconciliation:
    return RequestPdmReconciliation(repo=repo, uow=uow)


def get_pdm_reconciliation_use_case(
    run_repo: IPdmSyncRunRepository = Depends(get_pdm_sync_run_repo),
    finding_repo: IPdmReconciliationFindingRepository = Depends(
        get_pdm_reconciliation_finding_repo
    ),
) -> GetPdmReconciliation:
    return GetPdmReconciliation(run_repo=run_repo, finding_repo=finding_repo)


def get_list_pdm_reconciliation_findings_use_case(
    run_repo: IPdmSyncRunRepository = Depends(get_pdm_sync_run_repo),
    finding_repo: IPdmReconciliationFindingRepository = Depends(
        get_pdm_reconciliation_finding_repo
    ),
) -> ListPdmReconciliationFindings:
    return ListPdmReconciliationFindings(run_repo=run_repo, finding_repo=finding_repo)
