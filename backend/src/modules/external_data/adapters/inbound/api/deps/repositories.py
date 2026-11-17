"""Repository factories on the request's session, and the module's settings
store."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.external_data.adapters.outbound.persistence.repositories.external_data_settings_repository import (
    SqlAlchemyExternalDataSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_document_link_repository import (
    SqlAlchemyPdmDocumentLinkRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_reconciliation_finding_repository import (
    SqlAlchemyPdmReconciliationFindingRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
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
from src.modules.platform.adapters.inbound.api.deps.database import repo_factory

get_pdm_file_snapshot_repo: Callable[[AsyncSession], IPdmFileSnapshotRepository] = repo_factory(
    SqlAlchemyPdmFileSnapshotRepository
)
get_pdm_sync_run_repo: Callable[[AsyncSession], IPdmSyncRunRepository] = repo_factory(
    SqlAlchemyPdmSyncRunRepository
)
get_pdm_document_link_repo: Callable[[AsyncSession], IPdmDocumentLinkRepository] = repo_factory(
    SqlAlchemyPdmDocumentLinkRepository
)
get_pdm_reconciliation_finding_repo: Callable[
    [AsyncSession], IPdmReconciliationFindingRepository
] = repo_factory(SqlAlchemyPdmReconciliationFindingRepository)

get_external_data_settings_repo: Callable[[AsyncSession], IExternalDataSettingsRepository] = (
    repo_factory(SqlAlchemyExternalDataSettingsRepository)
)
