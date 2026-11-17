"""
Repository interface for PdmFileSnapshot, the diff base the PDM poller
runs against. PdmFileSnapshotFilterDto lives here, like every repository
filter DTO, because ports may not import application; pdm_dto.py holds its
pydantic mirror.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot


@dataclass
class PdmFileSnapshotFilterDto:
    skip: int | None = None
    limit: int | None = None
    sync_state: str | None = None
    kind: str | None = None
    search: str | None = None  # matches name, path, part_number


@runtime_checkable
class IPdmFileSnapshotRepository(Protocol):
    async def get_by_file(self, vault_id: str, file_id: int) -> PdmFileSnapshot | None: ...
    async def get_by_id(self, id: int) -> PdmFileSnapshot | None: ...
    async def find_by_path_suffix(self, vault_id: str, path_suffix: str) -> PdmFileSnapshot | None:
        """The snapshot of `vault_id` whose vault-relative `path` is a
        case-insensitive suffix of `path_suffix`, a caller's full local path.
        The longest match wins, because a shallower path is a suffix of a
        deeper one too; no match or a tie for the longest returns None."""
        ...

    async def upsert_many(self, items: list[PdmFileSnapshot]) -> None:
        """Inserts new rows and updates existing ones, matched on (vault_id,
        file_id). It reads the existing rows in chunked IN queries and writes
        through the session instead of a dialect-specific upsert, so it runs the
        same on SQLite and Postgres and keeps loaded rows current."""
        ...

    async def get_by_file_ids(self, vault_id: str, file_ids: list[int]) -> list[PdmFileSnapshot]:
        """The rows of `vault_id` for `file_ids`, in chunked IN queries. The
        poller reads one watched folder's files this way instead of the
        whole vault."""
        ...

    async def get_by_parent_folder_ids(
        self, vault_id: str, folder_ids: list[int]
    ) -> list[PdmFileSnapshot]:
        """The rows of `vault_id` whose parent folder is one of `folder_ids`,
        for the poller's missing-file sweep over the folders it walked."""
        ...

    async def get_multi(
        self, filters: PdmFileSnapshotFilterDto
    ) -> tuple[int, list[PdmFileSnapshot]]:
        """Paged, filtered by sync_state/kind and a search term matching
        name/path/part_number, sorted last_seen_at desc."""
        ...

    async def get_all_for_vault(self, vault_id: str) -> list[PdmFileSnapshot]:
        """Every snapshot row of `vault_id`, unpaged, in one query, for the
        callers that genuinely need the whole vault: the deep reconciliation
        (ReconcilePdmVault) and a watched-folder change in the PDM settings.
        The poller reads per walked folder instead (get_by_parent_folder_ids,
        get_by_file_ids)."""
        ...

    async def get_preview_candidates(self, vault_id: str, kind: str) -> list[PdmFileSnapshot]:
        """Rows of `kind` with a part number that are not missing and either
        have no item link or a version newer than the one last ingested: the
        only rows the catalogue preview can report, selected in SQL so a
        large vault is never loaded whole for it."""
        ...

    async def list_conflicts(self, vault_id: str) -> list[PdmFileSnapshot]:
        """Every row of `vault_id` with sync_state = conflict, for the
        end-of-run parked-conflict retry (docs/reference/field-ownership.md section 5)."""
        ...

    async def reset_skipped_to_pending(self, vault_id: str) -> int:
        """Requeues every skipped row of `vault_id` as pending, clears last_error
        and returns the number of rows changed. UpdatePdmSettings calls it after
        a change to the fields that decide eligibility, so a file skipped for a
        settings reason is picked up by the next poll; rows outside every
        watched folder are marked missing first."""
        ...

    async def save(self, item: PdmFileSnapshot) -> PdmFileSnapshot: ...
    async def counts_by_state(self, vault_id: str) -> dict[str, int]:
        """sync_state -> row count for `vault_id`, for the admin settings
        page's snapshot_counts summary."""
        ...
