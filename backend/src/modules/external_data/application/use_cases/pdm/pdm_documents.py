"""
Documents and thumbnails (docs/reference/pdm-documents.md): PdmDocumentSync
handles a `documents` watched folder's exported files (drawing PDFs, DXF,
STEP...), and PdmThumbnails fetches a made/bought file's own PDM
thumbnail after a successful ingest. Both are best-effort, per-file
helpers invoked by PollPdmVault and RefreshPdmFile; neither ever raises
for a business outcome, only for a genuine programming/transport error a
repository itself would raise. They live with the PDM use cases because
PdmDocumentSync drives the item file upload use cases and commits per file.

PdmDocumentSync.sync_one is the poller's/refresh's entry point for one
file found under a `documents` folder. Such a file is never ingested as
its own catalogue row: it is matched to an EXISTING made or bought item
and stored as one of that item's attachments through the existing
UploadMadeItemFile/UploadBoughtItemFile use case (as the system user, the
same actor IngestPdmFile uses), which gives the "replace on version
change" behaviour for free: the target category (drawing/DXF/step) is a
singleton slot, so uploading again simply replaces whatever was there. An
`image_and_thumbnail` document is stored as the item's CAD rendering
instead (ItemPictureStore), which likewise replaces only the previous CAD
rendering, never a photo or the Data Portal picture.
Matching is by (part_number, revision) for a made item, by part_number
alone for a bought item: part numbers are unique app-wide, so an
unresolved kind tries made then bought and can never match both. Identity
comes from the folder's own `match_by`:
  - "datacard": the file's own mapped variables (map_variables against
    both the made and bought maps, since a document can equally be an export
    of either family), kind from the same `Glados.Kind` variable ingest
    itself reads (pdm_variables.kind_variable_name).
  - "filename": `filename_pattern`'s named groups (`part_number`,
    `revision`, optional `kind`) against the bare file name.
The extension (after identity, matching FIELD_OWNERSHIP's own rule
ordering) resolves the file category via `document_categories`; an
unmapped extension is `skipped`, never an error, and so is an extension
`document_excluded_kinds` excludes for the matched item's kind.

Every outcome updates the same PdmFileSnapshot row the caller already
upserted for the scan (kind "document" per that entity's docstring) with
this call's own result (sync_state, part_number, revision, item_id,
last_ingested_version); the same two-phase write IngestPdmFile itself
uses (scan fields now, outcome fields once resolved). One transaction per
file, committed here.

PdmThumbnails.after_ingest mirrors PdmWriteBack.after_outcome's shape and
call sites exactly (see poll_pdm_vault.py/refresh_pdm_file.py): a no-op
unless `thumbnails_enabled`, the outcome is linked to a made/bought item,
and the ingest actually performed a synced write (`_THUMBNAIL_ACTIONS`,
the same "the PDM version just changed" condition PdmWriteBack's own
_SYNCED_ACTIONS encodes). A missing thumbnail (PDM has none rendered,
the common case absent a Convert task) is a quiet no-op, not an error;
only a genuine transport/storage failure records `thumbnail_error`. The
thumbnail becomes the item's CAD rendering only while no exported image
document has supplied one, since that document is the full-size rendering
and the check-in thumbnail is no more than a small preview.
"""

import re
from dataclasses import dataclass
from typing import Any

from src.modules.catalogue.application.facade.item_commands import ItemPictureStore
from src.modules.catalogue.application.facade.item_commands import StagedItemPicture
from src.modules.catalogue.application.facade.item_commands import UploadBoughtItemFile
from src.modules.catalogue.application.facade.item_commands import UploadMadeItemFile
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IItemPictureQueries
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_skip_reasons import (
    DOCUMENT_STATE_NOT_RELEASED,
)
from src.modules.external_data.application.services.pdm_skip_reasons import (
    document_kind_excluded_message,
)
from src.modules.external_data.application.services.pdm_variables import NO_FILE_LEVEL_CONFIGURATION
from src.modules.external_data.application.services.pdm_variables import kind_variable_name
from src.modules.external_data.application.services.pdm_variables import map_variables
from src.modules.external_data.application.services.pdm_variables import select_configuration
from src.modules.external_data.application.services.pdm_vault import file_extension
from src.modules.external_data.application.services.pdm_vault import sync_run_entry
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.value_objects.pdm_document_category import IMAGE_AND_THUMBNAIL
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmFileContent
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.repositories.pdm_document_link_repository import (
    IPdmDocumentLinkRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.application.services.file_attachments.base import StagedItemFile
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

# Category names that fall through to the shared "must be application/pdf"
# fallback (ItemFileKind.pdf_fallback_message) on both item families, see
# made_item/_file_kind.py and bought_item/_file_kind.py. Every other
# category (dxf, step) is extension-gated instead and does not care what
# content type is passed.
_PDF_LIKE_CATEGORIES = frozenset({"drawing", "pdf"})

# IngestOutcome.action values PdmThumbnails treats as "the file's PDM
# version just changed on the item"; mirrors PdmWriteBack's own
# _SYNCED_ACTIONS (pdm_writeback.py), the set of outcomes that follow a
# changed file through to an actual item write.
_THUMBNAIL_ACTIONS = frozenset({"created", "revised", "updated", "claimed", "status"})


def _upload_content_type(category_name: str) -> str:
    """The content type a document is uploaded under: PDF for the categories
    that require one, and a plain byte stream otherwise, which the
    extension-gated categories accept and every other category rejects with
    its own message."""
    if category_name in _PDF_LIKE_CATEGORIES:
        return "application/pdf"
    return "application/octet-stream"


@dataclass(frozen=True)
class _Identity:
    kind_hint: str | None  # "made" | "bought" | None (unresolved, try both)
    made_candidate: tuple[str, str] | None  # (part_number, revision)
    bought_candidate: str | None  # part_number


class PdmDocumentSync:
    def __init__(
        self,
        session: PdmSessionService,
        settings_repo: IExternalDataSettingsRepository,
        made_item_repo: IMadeItemCadStore,
        bought_item_repo: IBoughtItemCadStore,
        snapshot_repo: IPdmFileSnapshotRepository,
        document_link_repo: IPdmDocumentLinkRepository,
        user_repo: IUserRepository,
        *,
        upload_made_item_file: UploadMadeItemFile,
        upload_bought_item_file: UploadBoughtItemFile,
        picture_store: ItemPictureStore | None,
        uow: IUnitOfWork,
    ) -> None:
        self._session = session
        self._settings = settings_repo
        self._made_items = made_item_repo
        self._bought_items = bought_item_repo
        self._snapshots = snapshot_repo
        self._links = document_link_repo
        self._upload_made = upload_made_item_file
        self._upload_bought = upload_bought_item_file
        # None while storage is off; an image document then fails like any
        # other upload would.
        self._pictures = picture_store
        self._uow = uow
        self._users = user_repo
        # Resolved lazily by _system_actor, since a constructor cannot await
        # the repository; the first sync_one call fails loudly instead.
        self._actor: User | None = None

    async def _system_actor(self) -> User:
        if self._actor is None:
            actor = await self._users.get_by_username(SYSTEM_USER)
            if actor is None:
                raise RuntimeError(
                    "System user not found; init_db must seed it before PDM document sync can run."
                )
            self._actor = actor
        return self._actor

    # ── Entry point ──────────────────────────────────────────────────

    async def sync_one(
        self, *, vault_id: str, folder: PdmWatchedFolder, obj: PdmObjectInfo
    ) -> IngestOutcome:
        actor = await self._system_actor()
        settings = await self._settings.get_pdm()

        # Checked first, so an export still being worked on costs no
        # datacard read. A file synced earlier keeps its attachment.
        if obj.state_id not in settings.document_released_state_ids:
            return await self._finish(
                vault_id, obj, None, None, None, "skipped", DOCUMENT_STATE_NOT_RELEASED
            )

        identity, error = await self._resolve_identity(folder, obj, settings)
        if error is not None:
            return await self._finish(vault_id, obj, None, None, None, "skipped", error)
        assert identity is not None

        kind, item_id, part_number, revision = await self._resolve_item(identity)
        if kind is None or item_id is None:
            return await self._finish(
                vault_id, obj, None, None, None, "skipped", "no matching item"
            )

        extension = file_extension(obj.name)
        category_name = settings.document_categories.get(extension)
        if category_name is None:
            return await self._finish(
                vault_id, obj, kind, part_number, revision, "skipped", "extension not mapped"
            )
        # A file synced before the exclusion was set keeps its attachment,
        # the same rule a document leaving its released state follows.
        if not settings.ingests_document_for(extension, kind):
            return await self._finish(
                vault_id,
                obj,
                kind,
                part_number,
                revision,
                "skipped",
                document_kind_excluded_message(kind),
            )

        try:
            outcome, staged = await self._download_and_store(
                actor=actor,
                vault_id=vault_id,
                obj=obj,
                kind=kind,
                item_id=item_id,
                category_name=category_name,
            )
        except Exception as exc:
            log.warning("PDM document sync %s/%s failed: %s", vault_id, obj.id, exc)
            return await self._finish(
                vault_id, obj, kind, part_number, revision, "document_error", str(exc)
            )

        # The file rows, their document link and the snapshot commit together
        # in _finish, so a failure in between can never leave a file the next
        # poll would not recognise as already synced and upload again.
        try:
            result = await self._finish(
                vault_id, obj, kind, part_number, revision, "document", outcome, item_id=item_id
            )
        except Exception:
            await self._uow.rollback()
            await self._discard(kind, staged)
            raise
        await self._complete(kind, staged)
        return result

    async def _complete(self, kind: str, staged: StagedItemFile[Any] | StagedItemPicture) -> None:
        if isinstance(staged, StagedItemPicture):
            assert self._pictures is not None  # a staged picture implies the store
            await self._pictures.finish(staged)
        else:
            await self._uploader(kind).finish_staged(staged)

    async def _discard(self, kind: str, staged: StagedItemFile[Any] | StagedItemPicture) -> None:
        if isinstance(staged, StagedItemPicture):
            assert self._pictures is not None  # a staged picture implies the store
            await self._pictures.discard(staged)
        else:
            await self._uploader(kind).discard_staged(staged)

    def _uploader(self, kind: str) -> UploadMadeItemFile | UploadBoughtItemFile:
        return self._upload_made if kind == "made" else self._upload_bought

    # ── Identity resolution ──────────────────────────────────────────

    async def _resolve_identity(
        self, folder: PdmWatchedFolder, obj: PdmObjectInfo, settings: AdminPdmSettings
    ) -> tuple[_Identity | None, str | None]:
        if folder.match_by == "filename":
            return self._resolve_identity_by_filename(folder, obj)
        return await self._resolve_identity_by_datacard(obj, settings)

    def _resolve_identity_by_filename(
        self, folder: PdmWatchedFolder, obj: PdmObjectInfo
    ) -> tuple[_Identity | None, str | None]:
        pattern = re.compile(folder.filename_pattern or "")
        match = pattern.search(obj.name)
        if match is None:
            return None, "filename does not match the configured pattern"
        groups = match.groupdict()
        part_number = (groups.get("part_number") or "").strip()
        revision = (groups.get("revision") or "").strip()
        kind_hint = (groups.get("kind") or "").strip() or None
        if kind_hint not in ("made", "bought"):
            kind_hint = None
        if not part_number:
            return None, "identity variables missing"
        made_candidate = (part_number, revision) if revision else None
        return _Identity(
            kind_hint=kind_hint, made_candidate=made_candidate, bought_candidate=part_number
        ), None

    async def _resolve_identity_by_datacard(
        self, obj: PdmObjectInfo, settings: AdminPdmSettings
    ) -> tuple[_Identity | None, str | None]:
        async def _do(gw: IPdmGateway, token: str) -> list[PdmConfigVariables]:
            return await gw.file_variables(token, obj.id, obj.version, obj.parent_folder_id)

        configs = await self._session.call(_do)
        variables = select_configuration(configs)
        if variables is None:
            return None, NO_FILE_LEVEL_CONFIGURATION

        raw_kind = (variables.get(kind_variable_name(settings)) or "").strip()
        kind_hint = raw_kind if raw_kind in ("made", "bought") else None

        made_mapped = map_variables("made", settings.made_item_variable_map, variables)
        bought_mapped = map_variables("bought", settings.bought_item_variable_map, variables)
        made_part_number = (made_mapped.get("part_number") or "").strip()
        made_revision = (made_mapped.get("revision") or "").strip()
        bought_part_number = (bought_mapped.get("part_number") or "").strip()

        made_candidate = (
            (made_part_number, made_revision) if made_part_number and made_revision else None
        )
        bought_candidate = bought_part_number or None
        if made_candidate is None and bought_candidate is None:
            return None, "identity variables missing"
        return _Identity(
            kind_hint=kind_hint, made_candidate=made_candidate, bought_candidate=bought_candidate
        ), None

    async def _resolve_item(
        self, identity: _Identity
    ) -> tuple[str | None, int | None, str | None, str | None]:
        """Returns (kind, item_id, part_number, revision) for the first
        match, trying only `kind_hint` when known, else made then bought;
        part numbers are unique app-wide so at most one of the two can
        ever match."""
        order = [identity.kind_hint] if identity.kind_hint else ["made", "bought"]
        for kind in order:
            if kind == "made" and identity.made_candidate is not None:
                made_part_number, made_revision = identity.made_candidate
                made_item = await self._made_items.get_by_part_number_and_revision(
                    made_part_number, made_revision
                )
                if made_item is not None:
                    return "made", made_item.id, made_part_number, made_revision
            if kind == "bought" and identity.bought_candidate is not None:
                bought_part_number = identity.bought_candidate
                bought_item = await self._bought_items.get_by_part_number(bought_part_number)
                if bought_item is not None:
                    return "bought", bought_item.id, bought_part_number, None
        no_match_part_number: str | None = (
            identity.made_candidate[0] if identity.made_candidate else identity.bought_candidate
        )
        no_match_revision = identity.made_candidate[1] if identity.made_candidate else None
        return None, None, no_match_part_number, no_match_revision

    # ── Download + store ─────────────────────────────────────────────

    async def _download_and_store(
        self,
        *,
        actor: User,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str,
        item_id: int,
        category_name: str,
    ) -> tuple[str, StagedItemFile[Any] | StagedItemPicture]:
        """Downloads the document and stages its file row (or, for an
        `image_and_thumbnail` document, its CAD rendering) and its document
        link without committing; the caller commits them with the snapshot.
        On any failure here the staged writes are rolled back and the stored
        blobs removed before the error propagates."""

        async def _do(gw: IPdmGateway, token: str) -> PdmFileContent:
            return await gw.download_file(token, obj.id, obj.version, obj.parent_folder_id)

        content = await self._session.call(_do)

        staged: StagedItemFile[Any] | StagedItemPicture
        if category_name == IMAGE_AND_THUMBNAIL:
            if self._pictures is None:
                raise StorageNotEnabledError("Storage is not enabled.")
            staged = await self._pictures.stage(
                ItemKind(kind),
                item_id,
                ItemPictureSource.CAD_RENDERING,
                content.data,
                obj.name,
                actor.id,
            )
            stored = f"CAD rendering #{staged.picture.id}"
        else:
            staged = await self._stage(actor, kind, item_id, obj.name, content.data, category_name)
            stored = f"{staged.file.category.value} file #{staged.file.id}"

        try:
            link = await self._links.get_by_pdm_file(vault_id, obj.id)
            await self._links.upsert(
                PdmDocumentLink(
                    id=link.id if link is not None else 0,
                    kind=ItemKind(kind),
                    item_id=item_id,
                    item_file_id=staged.file.id if isinstance(staged, StagedItemFile) else None,
                    vault_id=vault_id,
                    file_id=obj.id,
                    version=obj.version,
                    item_picture_id=(
                        staged.picture.id if isinstance(staged, StagedItemPicture) else None
                    ),
                )
            )
        except Exception:
            await self._uow.rollback()
            await self._discard(kind, staged)
            raise
        return f"stored as {stored} ({len(content.data)} bytes).", staged

    async def _stage(
        self,
        actor: User,
        kind: str,
        item_id: int,
        file_name: str,
        data: bytes,
        category_name: str,
    ) -> StagedItemFile[Any]:
        content_type = _upload_content_type(category_name)
        if kind == "made":
            return await self._upload_made.stage(
                actor=actor,
                item_id=item_id,
                data=data,
                file_name=file_name,
                content_type=content_type,
                category=MadeItemFileCategory(category_name),
            )
        return await self._upload_bought.stage(
            actor=actor,
            item_id=item_id,
            data=data,
            file_name=file_name,
            content_type=content_type,
            category=BoughtItemFileCategory(category_name),
        )

    # ── Snapshot outcome ──────────────────────────────────────────────

    async def _finish(
        self,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str | None,
        part_number: str | None,
        revision: str | None,
        action: str,
        message: str,
        *,
        item_id: int | None = None,
    ) -> IngestOutcome:
        snapshot = await self._snapshots.get_by_file(vault_id, obj.id)
        if snapshot is not None:
            snapshot.sync_state = (
                PdmFileSyncState.INGESTED
                if action == "document"
                else PdmFileSyncState.ERROR
                if action == "document_error"
                else PdmFileSyncState.SKIPPED
            )
            snapshot.last_error = None if action == "document" else message
            snapshot.part_number = part_number
            snapshot.revision = revision
            snapshot.item_id = item_id
            if action == "document":
                snapshot.last_ingested_version = obj.version
            await self._snapshots.upsert_many([snapshot])
        # Commits even without a snapshot row: a synced document's staged
        # file row and link are committed here.
        await self._uow.commit()
        return IngestOutcome(action=action, item_id=item_id, message=message)


class PdmThumbnails:
    def __init__(
        self,
        session: PdmSessionService,
        settings_repo: IExternalDataSettingsRepository,
        picture_repo: IItemPictureQueries,
        picture_store: ItemPictureStore | None,
        user_repo: IUserRepository,
        run_repo: IPdmSyncRunRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._session = session
        self._settings = settings_repo
        self._picture_repo = picture_repo
        # None while storage is off, which makes every call a no-op.
        self._pictures = picture_store
        self._users = user_repo
        self._runs = run_repo
        self._uow = uow

    async def after_ingest(
        self,
        vault_id: str,
        file: PdmObjectInfo,
        kind: str,
        outcome: IngestOutcome,
        run: PdmSyncRun,
    ) -> str | None:
        if outcome.item_id is None or kind not in ("made", "bought"):
            return None
        if outcome.action not in _THUMBNAIL_ACTIONS:
            return None
        settings = await self._settings.get_pdm()
        if not settings.thumbnails_enabled or self._pictures is None:
            return None
        item_kind = ItemKind(kind)
        current = await self._picture_repo.get_by_source(
            item_kind, outcome.item_id, ItemPictureSource.CAD_RENDERING
        )
        if current is not None and current.image_path is not None:
            # An exported image document already is this item's full-size
            # CAD rendering; the check-in thumbnail would only shrink it.
            return None

        async def _do(gw: IPdmGateway, token: str) -> PdmFileContent | None:
            return await gw.download_thumbnail(token, file.id, file.version, file.parent_folder_id)

        staged: StagedItemPicture | None = None
        try:
            content = await self._session.call(_do)
            if content is None:
                return None
            actor = await self._users.get_by_username(SYSTEM_USER)
            if actor is None:
                raise RuntimeError("System user not found; init_db must seed it first.")
            staged = await self._pictures.stage(
                item_kind,
                outcome.item_id,
                ItemPictureSource.CAD_RENDERING,
                content.data,
                file.name,
                actor.id,
                thumbnail_only=True,
            )
            await self._record(
                run,
                vault_id,
                file,
                kind,
                outcome.item_id,
                "thumbnail",
                f"stored thumbnail ({len(content.data)} bytes).",
            )
            await self._uow.commit()
        except Exception as exc:
            log.warning("PDM thumbnail %s/%s failed: %s", vault_id, file.id, exc)
            await self._uow.rollback()
            if staged is not None:
                await self._pictures.discard(staged)
            await self._record(
                run, vault_id, file, kind, outcome.item_id, "thumbnail_error", str(exc)
            )
            return "thumbnail_error"
        await self._pictures.finish(staged)
        return "thumbnail"

    async def _record(
        self,
        run: PdmSyncRun,
        vault_id: str,
        file: PdmObjectInfo,
        kind: str,
        item_id: int,
        action: str,
        message: str,
    ) -> None:
        await self._runs.add_entries(
            run.id,
            [sync_run_entry(run.id, vault_id, file, kind, action, item_id, message)],
        )
