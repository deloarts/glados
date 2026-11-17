"""
Backs GET /web/pdm/preview: the catalogue's read-only view of PDM files
that exist in the vault but are not (yet) fully reflected in Glados,
either because nothing was ever ingested for them (`unlinked`) or because
the vault has moved on to a newer version since the last successful
ingest (`newer`). Purely a read over pdm_file_snapshot_table cross-checked
against the live made/bought catalogue; it creates nothing and is not an
item status.

Permission: mirrors the made/bought item list endpoints (GetMadeItems,
GetBoughtItems), neither of which gates reads by permission: any
authenticated active user can already see the full catalogue, so there is
nothing further to assert here. Same reasoning as GetLookups's docstring
for the six PAT list endpoints it replaces.
"""

from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.external_data.application.dto.pdm_preview_dto import PdmPreviewFileResult
from src.modules.external_data.application.dto.pdm_preview_dto import PdmPreviewNewerResult
from src.modules.external_data.application.dto.pdm_preview_dto import PdmPreviewResult
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.platform.domain.entities.user import User


class ListPdmPreview:
    def __init__(
        self,
        snapshot_repo: IPdmFileSnapshotRepository,
        made_item_repo: IMadeItemCadStore,
        bought_item_repo: IBoughtItemCadStore,
        admin_settings_repo: IExternalDataSettingsRepository,
    ) -> None:
        self._snapshots = snapshot_repo
        self._made_items = made_item_repo
        self._bought_items = bought_item_repo
        self._admin_settings = admin_settings_repo

    async def execute(self, actor: User, kind: str) -> PdmPreviewResult:
        pdm_settings = await self._admin_settings.get_pdm()
        if not pdm_settings.enabled or not pdm_settings.vault_id:
            return PdmPreviewResult(kind=kind, enabled=False, unlinked=[], newer=[])

        rows = await self._snapshots.get_preview_candidates(pdm_settings.vault_id, kind)
        unlinked_rows = [r for r in rows if r.item_id is None and r.part_number]
        live = await self._live_part_numbers(kind, [r.part_number or "" for r in unlinked_rows])

        unlinked = [
            PdmPreviewFileResult(
                file_id=row.file_id,
                name=row.name,
                path=row.path,
                part_number=row.part_number or "",
                revision=row.revision,
                article_name=row.article_name,
                version=row.version,
                state=row.state,
                modified_at=row.modified_at,
                sync_state=row.sync_state,
                last_error=row.last_error,
            )
            for row in unlinked_rows
            if row.part_number not in live
        ]

        newer: list[PdmPreviewNewerResult] = []
        for row in rows:
            if row.item_id is None or not row.part_number:
                continue
            item = (
                await self._made_items.get_by_id(row.item_id)
                if kind == "made"
                else await self._bought_items.get_by_id(row.item_id)
            )
            if item is None:
                continue
            if item.pdm_file_version is None or row.version > item.pdm_file_version:
                newer.append(
                    PdmPreviewNewerResult(
                        item_id=item.id,
                        item_public_id=item.public_id,
                        part_number=row.part_number,
                        revision=row.revision,
                        file_id=row.file_id,
                        name=row.name,
                        version=row.version,
                        state=row.state,
                        modified_at=row.modified_at,
                    )
                )

        return PdmPreviewResult(kind=kind, enabled=True, unlinked=unlinked, newer=newer)

    async def _live_part_numbers(self, kind: str, part_numbers: list[str]) -> set[str]:
        """Which of `part_numbers` already belong to a live item, in one batch
        query: such a file is already in the catalogue, just not linked yet."""
        if not part_numbers:
            return set()
        if kind == "made":
            return await self._made_items.existing_part_numbers(part_numbers)
        return await self._bought_items.existing_part_numbers(part_numbers)
