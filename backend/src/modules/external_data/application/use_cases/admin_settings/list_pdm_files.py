"""
Backs the admin "PDM files" pending list (GET /admin/settings/pdm/files):
a paged, filtered read of every watched file the poller has ever seen and
where it currently stands in the poll -> ingest pipeline. Each row names the
catalogue its item belongs to, so the list can link to it. Read-only, no
call to the vault.
"""

from src.modules.external_data.application.dto.pdm_dto import PdmFileSnapshotFilterDto
from src.modules.external_data.application.dto.pdm_dto import PdmFileSnapshotResult
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm_vault import (
    PdmVaultMapper,
)
from src.modules.external_data.application.services.pdm_snapshot_item_kind import (
    snapshot_item_kinds,
)
from src.modules.external_data.ports.outbound.repositories.pdm_document_link_repository import (
    IPdmDocumentLinkRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    PdmFileSnapshotFilterDto as PdmFileSnapshotFilterPort,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class ListPdmFiles:
    def __init__(
        self,
        repo: IPdmFileSnapshotRepository,
        document_link_repo: IPdmDocumentLinkRepository | None = None,
    ) -> None:
        self._repo = repo
        self._links = document_link_repo

    async def execute(
        self, actor: User, filters: PdmFileSnapshotFilterDto
    ) -> tuple[int, list[PdmFileSnapshotResult]]:
        SettingsRules.assert_can_read(actor)

        total, rows = await self._repo.get_multi(
            PdmFileSnapshotFilterPort(
                skip=filters.skip,
                limit=filters.limit,
                sync_state=filters.sync_state,
                kind=filters.kind,
                search=filters.search,
            )
        )
        item_kinds = await snapshot_item_kinds(rows, self._links)
        return total, [
            PdmVaultMapper.pdm_file_snapshot_to_result(r, item_kinds[r.id]) for r in rows
        ]
