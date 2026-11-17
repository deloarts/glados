"""The folder walk of the PDM poll: resolving a watched folder's root,
browsing it and its subfolders, and dropping the files the file type rule
does not admit. The behaviour is documented in docs/reference/pdm-sync.md
sections 3.2 and 3.7.

A failed root browse returns no files and reports the root as not walked, so
the caller skips that folder's missing sweep and cadence update. PollFolderWalk
is a base class of PollPdmVault and reads the dependencies its constructor
sets.
"""

from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_vault import file_extension
from src.modules.external_data.application.use_cases.pdm._poll_run import PollRunLog
from src.modules.external_data.application.use_cases.pdm._poll_run import PollSummary
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.errors import PdmUnavailableError
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.clock import now_utc

# PdmObjectInfo.object_type: 0 folder, 1 file, 3 BOM.
_FOLDER_OBJECT_TYPE = 0
_FILE_OBJECT_TYPE = 1

# The vault root's own folder id, PDM's fixed convention (never configured).
_VAULT_ROOT_FOLDER_ID = 1

# Watched-folder kind for documents (docs/reference/pdm-documents.md section 2):
# every file in such a folder is a document candidate, matched
# to an existing item rather than ingested itself. See
# application.use_cases.pdm.pdm_documents.PdmDocumentSync.
_DOCUMENTS_FOLDER_KIND = "documents"


class _FolderNotFoundError(Exception):
    """Raised internally when a watched folder's path cannot be resolved to
    a folder id: some path segment matches no live subfolder of its parent
    (the folder was renamed or deleted in PDM). Caught by `_walk_folder`
    alongside PdmApiError/PdmUnavailableError: any of the three means the
    watched root cannot be reached this run, so it gets the same "record
    and skip the sweep" treatment rather than risking a false mass
    "missing" on what might just be a transient rename in progress."""


class PollFolderWalk(PollRunLog):
    """The folder walk; PollPdmVault sets every attribute declared here."""

    _session: PdmSessionService

    async def _resolve_folder_id(self, path: str) -> int:
        """The watched folder's own id, found by browsing down from the
        vault root one path segment at a time (never cached: the value
        object stays a plain path, resolved fresh every run). Raises
        `_FolderNotFoundError` when a segment matches no live subfolder of
        its parent."""
        segments = [s for s in path.split("\\") if s]
        current_id = _VAULT_ROOT_FOLDER_ID
        for segment in segments:
            children = await self._browse(current_id)
            match = next(
                (
                    c
                    for c in children
                    if c.object_type == _FOLDER_OBJECT_TYPE
                    and not c.is_deleted
                    and c.name.lower() == segment.lower()
                ),
                None,
            )
            if match is None:
                raise _FolderNotFoundError(f"folder segment {segment!r} of {path!r} not found")
            current_id = match.id
        return current_id

    async def _resolve_root_id(
        self, vault_id: str, folder: PdmWatchedFolder, run: PdmSyncRun, summary: PollSummary
    ) -> int:
        """The id to walk `folder` from. The configured path is resolved fresh
        on every run, so a folder that was deleted and recreated under the same
        path in PDM is still found. The stored `folder_id` covers the opposite
        case, a folder renamed or moved in PDM whose configured path no longer
        resolves. When the two disagree the walk still goes ahead, but the run
        records an error entry, since the admin should pick the folder again.
        Raises when neither yields a folder."""
        if folder.folder_id is None:
            return await self._resolve_folder_id(folder.path)
        try:
            resolved = await self._resolve_folder_id(folder.path)
        except (PdmApiError, _FolderNotFoundError) as exc:
            await self._record_folder_drift(
                vault_id,
                folder,
                run,
                summary,
                f"configured path no longer resolves ({exc}), walking the stored folder id "
                f"{folder.folder_id} instead; pick the folder again in the PDM settings",
            )
            return folder.folder_id
        if resolved != folder.folder_id:
            await self._record_folder_drift(
                vault_id,
                folder,
                run,
                summary,
                f"stored folder id {folder.folder_id} no longer matches the configured path, "
                f"walking folder id {resolved} instead; pick the folder again in the PDM settings",
            )
        return resolved

    async def _record_folder_drift(
        self,
        vault_id: str,
        folder: PdmWatchedFolder,
        run: PdmSyncRun,
        summary: PollSummary,
        message: str,
    ) -> None:
        log.warning("PDM poll: watched folder %r: %s", folder.path, message)
        summary.errors += 1
        entry = self._folder_error_entry(
            run.id, vault_id, folder.folder_id or 0, folder.path, message
        )
        await self._runs.add_entries(run.id, [entry])
        await self._uow.commit()

    async def _browse(self, folder_id: int) -> list[PdmObjectInfo]:
        async def _do(gw: IPdmGateway, token: str) -> list[PdmObjectInfo]:
            return await gw.browse_folder(token, folder_id)

        return await self._session.call(_do)

    @staticmethod
    def _admitted_extensions(folder_kind: str, settings: AdminPdmSettings) -> frozenset[str] | None:
        """The file-type rule (docs/reference/pdm-documents.md section 1): the
        set of lower-case, dot-free extensions a
        made/bought/by_kind folder actually admits as candidates. None
        (no filter at all) for a `documents` folder, which snapshots
        every file regardless of extension: its own gate is
        document_categories, applied per file once matched."""
        if folder_kind == _DOCUMENTS_FOLDER_KIND:
            return None
        made = frozenset(settings.made_item_extensions)
        bought = frozenset(settings.bought_item_extensions)
        if folder_kind == "made":
            return made
        if folder_kind == "bought":
            return bought
        return made | bought  # by_kind: union until the kind is known

    async def _walk_folder(
        self,
        vault_id: str,
        folder: PdmWatchedFolder,
        run: PdmSyncRun,
        summary: PollSummary,
        settings: AdminPdmSettings,
        folder_membership: dict[int, PdmWatchedFolder],
    ) -> tuple[list[PdmObjectInfo], bool, int]:
        """Resolves and browses `folder`'s own root, then recurses into
        every subfolder when `folder.recursive`. The root id comes from
        `_resolve_root_id`. Returns the files found (deleted entries
        already dropped, and, for a made/bought/by_kind folder, files
        whose extension the file-type rule does not admit also dropped,
        tallied into `summary.ignored_by_type` rather than appended),
        whether the root itself could be browsed at all, and the number of
        folders successfully browsed (the walk's own cost, not counting
        the ancestor lookups a name-walk fallback spends finding the
        root's id). Every folder id actually browsed, root and every
        subfolder recursed into, is recorded into `folder_membership`
        against `folder` itself, for _sweep_missing's own attribution."""
        try:
            root_id = await self._resolve_root_id(vault_id, folder, run, summary)
            root_children = await self._browse(root_id)
        except (PdmApiError, PdmUnavailableError, _FolderNotFoundError) as exc:
            message = f"could not browse watched folder {folder.path!r}: {exc}"
            log.warning("PDM poll: %s", message)
            summary.errors += 1
            await self._runs.add_entries(
                run.id, [self._folder_error_entry(run.id, vault_id, 0, folder.path, message)]
            )
            await self._uow.commit()
            return [], False, 0

        admitted = self._admitted_extensions(folder.kind, settings)
        files: list[PdmObjectInfo] = []
        visited = {root_id}
        folder_membership[root_id] = folder
        walked = 1 + await self._walk_children(
            vault_id,
            root_children,
            folder,
            files,
            visited,
            run,
            summary,
            admitted,
            folder_membership,
        )
        return files, True, walked

    async def _walk_children(
        self,
        vault_id: str,
        children: list[PdmObjectInfo],
        folder: PdmWatchedFolder,
        files: list[PdmObjectInfo],
        visited: set[int],
        run: PdmSyncRun,
        summary: PollSummary,
        admitted: frozenset[str] | None,
        folder_membership: dict[int, PdmWatchedFolder],
    ) -> int:
        walked = 0
        for child in children:
            if child.is_deleted:
                continue
            if child.object_type == _FILE_OBJECT_TYPE:
                if admitted is not None and file_extension(child.name) not in admitted:
                    summary.ignored_by_type += 1
                    continue
                files.append(child)
            elif child.object_type == _FOLDER_OBJECT_TYPE:
                if not folder.recursive or child.id in visited:
                    continue
                visited.add(child.id)
                folder_membership[child.id] = folder
                run.current_path = child.path
                await self._save_progress(run, summary)
                try:
                    grandchildren = await self._browse(child.id)
                except (PdmApiError, PdmUnavailableError) as exc:
                    message = f"could not browse folder {child.path!r}: {exc}"
                    log.warning("PDM poll: %s", message)
                    summary.errors += 1
                    await self._runs.add_entries(
                        run.id,
                        [self._folder_error_entry(run.id, vault_id, child.id, child.path, message)],
                    )
                    await self._uow.commit()
                    continue
                walked += 1
                walked += await self._walk_children(
                    vault_id,
                    grandchildren,
                    folder,
                    files,
                    visited,
                    run,
                    summary,
                    admitted,
                    folder_membership,
                )
        return walked

    @staticmethod
    def _folder_error_entry(
        run_id: int, vault_id: str, folder_id: int, path: str, message: str
    ) -> PdmSyncRunEntry:
        name = path.rsplit("\\", 1)[-1] if path else "(vault root)"
        return PdmSyncRunEntry(
            id=0,
            run_id=run_id,
            vault_id=vault_id,
            file_id=folder_id,
            name=name,
            path=path,
            kind=None,
            action="error",
            item_id=None,
            message=message,
            created_at=now_utc(),
        )
