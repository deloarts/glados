"""
DTOs for ListPdmPreview: the catalogue's read-only view of PDM files that
exist in the vault but have not (yet) been fully brought into Glados. Two
buckets, both derived from pdm_file_snapshot_table rather than any item
table, and neither creates or implies an item row:

- `unlinked`: a snapshot with no item link and no live item of the
  requested kind already carrying its part number: a file PDM knows about
  that Glados has never ingested.
- `newer`: a snapshot linked to an item whose ingested version is behind
  the vault's latest, i.e. someone released a new version in PDM since
  the last successful ingest.

PdmPreviewFileResult mirrors the file-identity subset of
PdmFileSnapshotResult (pdm_dto.py) plus `article_name`; it carries no
`id`/`public_id` of its own because the snapshot row's identity is not
part of this API's contract, only the file's.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PdmPreviewFileResult(BaseModel):
    file_id: int
    name: str
    path: str
    part_number: str
    revision: str | None
    article_name: str | None
    version: int
    state: str
    modified_at: datetime | None
    sync_state: str
    last_error: str | None


class PdmPreviewNewerResult(BaseModel):
    item_id: int
    item_public_id: UUID
    part_number: str
    revision: str | None
    file_id: int
    name: str
    version: int
    state: str
    modified_at: datetime | None


class PdmPreviewResult(BaseModel):
    kind: str
    enabled: bool
    unlinked: list[PdmPreviewFileResult]
    newer: list[PdmPreviewNewerResult]
