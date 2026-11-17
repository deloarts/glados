"""The steps both PDM ingest paths share: releaser attribution, field
resolution, the snapshot upsert and the skip, renumber, already-applied and
conflict outcomes.

IngestOutcomeRecorder is the base of MadeItemIngestion and
BoughtItemIngestion and holds these steps as methods, so both paths and
IngestPdmFile.execute() call them on the one use case instance. It declares
the dependencies it reads; IngestPdmFile's constructor sets them. Every
outcome method commits through commit_with_number_retry together with its
snapshot upsert, and business conditions come back as outcomes rather than
exceptions.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import PartNumberInUseError
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IPartNumberRegistryCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.pdm_field_resolution import find_other_kind_link
from src.modules.external_data.application.services.pdm_field_resolution import (
    resolve_article_group_ids,
)
from src.modules.external_data.application.services.pdm_field_resolution import resolve_existing_id
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_users import resolve_pdm_user
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.events.pdm_events import PdmFileIngested
from src.modules.external_data.domain.events.pdm_events import PdmIngestConflict
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmTransition
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc


def _mapped_article_name(mapped: dict[str, str]) -> str | None:
    """Normalizes `mapped["article_name"]` for the snapshot row the same
    way part_number/revision are normalized: "" (unmapped or blank on the
    card) becomes None rather than being stored as an empty string."""
    return (mapped.get("article_name") or "").strip() or None


@dataclass
class _PdmAttribution:
    """Resolved PDM releaser for one created/revised/claimed/status
    outcome (docs/reference/pdm-ingest.md section 5, "PDM releaser
    attribution"). The all-None default means "no
    attribution available" (no matching transition, or the read failed):
    callers then keep their existing system-actor changelog/changed_by_id
    behaviour untouched. `author_name` is the resolved Glados user's full
    name, or the raw PDM username as plain text when the vault user could
    not be resolved to one. `warning` folds a transitions read failure
    into the outcome message without ever failing the ingest for it."""

    resolved_user: User | None = None
    author_name: str | None = None
    transition_date: date | None = None
    transition_comment: str | None = None
    warning: str | None = None


def _version_guard_applies(
    item: MadeItem | BoughtItem, target_status: str, payload: PdmFilePayload
) -> bool:
    """Whether the linked row already reflects this file: it is at a newer
    version, or at the same version with the status the PDM state maps to. The
    same version at a different status still goes through, because a workflow
    transition does not necessarily create a new file version."""
    if item.pdm_file_version is None:
        return False
    if item.pdm_file_version > payload.file_version:
        return True
    return item.pdm_file_version == payload.file_version and item.status == target_status


def _drifted_number(item: MadeItem | BoughtItem | None, part_number: str) -> str | None:
    """The linked row's own part number when it differs from PDM's, else
    None. An empty number is reported as an empty string, so it still counts
    as drift."""
    if item is None or item.part_number == part_number:
        return None
    return item.part_number or ""


def _with_renumber_note(
    outcome: IngestOutcome,
    renumbered_from: str | None,
    part_number: str,
    item: MadeItem | BoughtItem | None,
) -> IngestOutcome:
    """Makes a renumbering visible in the run log. A file that was otherwise
    already in sync reports the renumbering as its update, so write-back
    and the run log see that the item changed."""
    if renumbered_from is None or item is None or outcome.action == "conflict":
        return outcome
    note = f"part number changed by PDM from {renumbered_from or '(none)'} to {part_number}"
    if outcome.action == "skipped" and outcome.item_id is None:
        return IngestOutcome(action="updated", item_id=item.id, message=note)
    return IngestOutcome(
        action=outcome.action, item_id=outcome.item_id, message=f"{note}; {outcome.message}"
    )


def _status_flip_without_item_reason(target_status: str) -> str:
    if target_status == "inactive":
        return "obsolete state without a matching item"
    return "replaced state without a matching item"


def _stamp_pdm_link(item: MadeItem | BoughtItem, payload: PdmFilePayload) -> None:
    """Writes the PDM link columns every successful ingest sets."""
    item.vault_id = payload.vault_id
    item.pdm_file_id = payload.file_id
    item.pdm_file_version = payload.file_version
    item.pdm_synced_at = now_utc()
    item.pdm_sync_state = PdmSyncState.SYNCED


def _successor_cleared_note(payload: PdmFilePayload) -> str:
    return f"successor cleared by PDM state {payload.state!r}."


def _outcome_message(base: str, *warnings: str | None) -> str:
    """Appends every non-empty warning to an outcome message."""
    return " ".join([base, *(w for w in warnings if w)])


class IngestOutcomeRecorder:
    """Shared ingest steps; IngestPdmFile sets every attribute declared here."""

    _made_items: IMadeItemCadStore
    _bought_items: IBoughtItemCadStore
    _article_groups: IArticleGroupQueries
    _admin_settings: IExternalDataSettingsRepository
    _snapshots: IPdmFileSnapshotRepository
    _user_repo: IUserRepository
    _user_pdm_links: IUserPdmLinkRepository
    _registry: IPartNumberRegistryCadStore
    _bus: IEventBus
    _uow: IUnitOfWork
    _session: PdmSessionService
    _actor_cache: User | None

    @property
    def _actor(self) -> User:
        assert self._actor_cache is not None  # resolved at the top of execute()
        return self._actor_cache

    async def _record_ingested(
        self,
        payload: PdmFilePayload,
        kind: str,
        item_id: int,
        action: str,
        part_number: str,
        revision: str | None,
        article_name: str | None,
    ) -> None:
        """Upserts the file's snapshot as ingested and stages PdmFileIngested, without
        committing."""
        await self._upsert_snapshot(
            payload,
            part_number,
            revision,
            item_id,
            PdmFileSyncState.INGESTED,
            None,
            article_name=article_name,
        )
        await self._publish_ingested(payload, kind, item_id, action, part_number, revision)

    async def _publish_ingested(
        self,
        payload: PdmFilePayload,
        kind: str,
        item_id: int,
        action: str,
        part_number: str,
        revision: str | None,
    ) -> None:
        await self._bus.publish(
            PdmFileIngested(
                vault_id=payload.vault_id,
                file_id=payload.file_id,
                kind=kind,
                item_id=item_id,
                action=action,
                part_number=part_number,
                revision=revision,
            )
        )

    def _log_write_outcome(self, payload: PdmFilePayload, outcome: IngestOutcome) -> None:
        """Shared by _made_create, _made_revise and _bought_create, whose
        merged write() closures have no common committing wrapper to log
        from."""
        log.info(
            f"PDM ingest {payload.vault_id}/{payload.file_id}: "
            f"{outcome.action} item #{outcome.item_id}."
        )

    async def _resolve_attribution(
        self,
        payload: PdmFilePayload,
        pdm_settings: AdminPdmSettings,
        kind: str,
        *,
        target_status: str,
    ) -> _PdmAttribution:
        """Reads the ingested version's transitions and picks the newest
        one whose destination state is in the released/obsolete/replaced
        state list for `kind` matching `target_status`: PDM's own record
        of who released (or obsoleted, or replaced) the file. Never
        raises: a transitions read failure (PDM unreachable, session
        expired, not configured) is logged at warning and treated the
        same as "no matching transition", so ingest always proceeds
        without PDM attribution rather than failing over it."""
        if target_status == "inactive":
            state_ids = pdm_settings.obsolete_state_ids_for(kind)
        elif target_status == "replaced":
            state_ids = pdm_settings.replaced_state_ids_for(kind)
        else:
            state_ids = pdm_settings.released_state_ids_for(kind)

        async def _call(gateway: IPdmGateway, token: str) -> list[PdmTransition]:
            return await gateway.file_transitions(
                token, payload.file_id, payload.file_version, payload.parent_folder_id
            )

        try:
            transitions = await self._session.call(_call)
        except DomainError as exc:
            log.warning(
                f"PDM ingest {payload.vault_id}/{payload.file_id}: could not read "
                f"transitions for releaser attribution: {exc}"
            )
            return _PdmAttribution(
                warning="PDM attribution unavailable (transitions could not be read)."
            )

        matching = [t for t in transitions if t.destination_state_id in state_ids]
        if not matching:
            return _PdmAttribution()

        newest = max(matching, key=lambda t: t.occurred_at)
        resolved = await resolve_pdm_user(
            self._user_pdm_links, self._user_repo, newest.user_id, newest.user_name
        )
        # The release day is the tenant's, like every day the app shows.
        zone = await tenant_zone(self._admin_settings)
        return _PdmAttribution(
            resolved_user=resolved,
            author_name=resolved.full_name if resolved is not None else newest.user_name,
            transition_date=as_utc(newest.occurred_at).astimezone(zone).date(),
            transition_comment=newest.comment or None,
        )

    async def _resolve_article_group_ids(
        self, mapped: dict[str, str]
    ) -> tuple[list[int], str | None]:
        """Delegates to application.services.pdm_field_resolution.
        resolve_article_group_ids, shared with ValidatePdmPayload."""
        return await resolve_article_group_ids(mapped, self._article_groups)

    async def _resolve_existing_id(
        self, mapped: dict[str, str], field: str, lookup: Callable[[int], Awaitable[object | None]]
    ) -> int | None:
        """Delegates to application.services.pdm_field_resolution.
        resolve_existing_id, shared with ValidatePdmPayload."""
        return await resolve_existing_id(mapped, field, lookup)

    async def _upsert_snapshot(
        self,
        payload: PdmFilePayload,
        part_number: str | None,
        revision: str | None,
        item_id: int | None,
        sync_state: PdmFileSyncState,
        last_error: str | None,
        parked_payload: dict[str, str] | None = None,
        article_name: str | None = None,
    ) -> None:
        now = now_utc()
        existing = await self._snapshots.get_by_file(payload.vault_id, payload.file_id)
        snapshot = existing or PdmFileSnapshot(
            id=0,
            vault_id=payload.vault_id,
            file_id=payload.file_id,
            kind=payload.kind,
            name=payload.name,
            path=payload.path,
            parent_folder_id=payload.parent_folder_id,
            version=payload.file_version,
            state_id=payload.state_id,
            state=payload.state,
            modified_at=payload.modified_at,
            first_seen_at=now,
            last_seen_at=now,
            last_ingested_version=None,
            sync_state=sync_state,
            last_error=last_error,
            part_number=part_number,
            revision=revision,
            item_id=item_id,
            parked_payload=parked_payload,
            article_name=article_name,
        )
        snapshot.kind = payload.kind
        snapshot.name = payload.name
        snapshot.path = payload.path
        snapshot.parent_folder_id = payload.parent_folder_id
        snapshot.version = payload.file_version
        snapshot.state_id = payload.state_id
        snapshot.state = payload.state
        snapshot.modified_at = payload.modified_at
        snapshot.last_seen_at = now
        snapshot.sync_state = sync_state
        snapshot.last_error = last_error
        snapshot.part_number = part_number
        snapshot.revision = revision
        snapshot.item_id = item_id
        snapshot.parked_payload = parked_payload
        snapshot.article_name = article_name
        if sync_state == PdmFileSyncState.INGESTED:
            snapshot.last_ingested_version = payload.file_version

        await self._snapshots.upsert_many([snapshot])

    async def _other_kind_link(
        self, vault_id: str, file_id: int, kind: str
    ) -> MadeItem | BoughtItem | None:
        """Delegates to application.services.pdm_field_resolution.
        find_other_kind_link; see execute()'s kind-changed guard, and
        that function's own docstring. Shared with ValidatePdmPayload's
        consistency check."""
        return await find_other_kind_link(
            self._made_items, self._bought_items, vault_id, file_id, kind
        )

    async def _skip(
        self,
        payload: PdmFilePayload,
        part_number: str | None,
        revision: str | None,
        reason: str,
        mapped: dict[str, str],
        item_id: int | None = None,
    ) -> IngestOutcome:
        async def write() -> IngestOutcome:
            await self._upsert_snapshot(
                payload,
                part_number,
                revision,
                item_id,
                PdmFileSyncState.SKIPPED,
                reason,
                article_name=_mapped_article_name(mapped),
            )
            return IngestOutcome(action="skipped", item_id=item_id, message=reason)

        return await commit_with_number_retry(self._uow, write, attempts=1)

    async def _renumber(
        self, kind: str, rows: Sequence[MadeItem | BoughtItem], part_number: str
    ) -> str | None:
        """Gives every linked row PDM's part number and returns None, or
        returns the conflict reason when the number already belongs to
        another item. The old number stays registered, since part numbers
        are never reused, and each row records the change in its changelog."""
        old_number = rows[0].part_number
        note = f"Part number changed by PDM from {old_number or '(none)'} to {part_number}."

        async def write() -> None:
            await self._registry.claim(part_number, kind)
            now = now_utc()
            for row in rows:
                row.part_number = part_number
                row.changed = now
                row.changes = append_changelog(row.changes, self._actor.full_name, note)
                if isinstance(row, MadeItem):
                    row.changed_by_id = self._actor.id
                    await self._made_items.save(row)
                else:
                    await self._bought_items.save(row)

        try:
            await commit_with_number_retry(self._uow, write, attempts=1)
        except PartNumberInUseError:
            await self._uow.rollback()
            for row in rows:
                row.part_number = old_number
            return f"part number {part_number} from PDM already belongs to another item"
        log.info("PDM ingest: %s item renumbered from %s to %s.", kind, old_number, part_number)
        return None

    async def _already_applied(
        self,
        payload: PdmFilePayload,
        part_number: str,
        revision: str | None,
        mapped: dict[str, str],
        item: MadeItem | BoughtItem,
    ) -> IngestOutcome:
        """Rule 6 outcome for a linked row that already reflects the file. The
        snapshot keeps its link either way. At the same version the file is in
        sync, so the snapshot reads ingested and the item synced again, which
        also settles a file that reappeared after being marked missing. A file
        behind the stored version stays a skip. The outcome names no item,
        because nothing was written to one, so write-back and the thumbnail
        fetch leave the vault alone."""
        reason = f"already at version {item.pdm_file_version}"
        in_sync = item.pdm_file_version == payload.file_version

        async def write() -> IngestOutcome:
            if in_sync and item.pdm_sync_state != PdmSyncState.SYNCED.value:
                item.pdm_sync_state = PdmSyncState.SYNCED
                if isinstance(item, MadeItem):
                    await self._made_items.save(item)
                else:
                    await self._bought_items.save(item)
            await self._upsert_snapshot(
                payload,
                part_number,
                revision,
                item.id,
                PdmFileSyncState.INGESTED if in_sync else PdmFileSyncState.SKIPPED,
                None if in_sync else reason,
                article_name=_mapped_article_name(mapped),
            )
            return IngestOutcome(action="skipped", item_id=None, message=reason)

        return await commit_with_number_retry(self._uow, write, attempts=1)

    async def _conflict(
        self,
        payload: PdmFilePayload,
        part_number: str | None,
        revision: str | None,
        reason: str,
        mapped: dict[str, str],
        item: MadeItem | BoughtItem | None = None,
        item_kind: str | None = None,
    ) -> IngestOutcome:
        """`item_kind` names which repository owns `item`, when it differs
        from `payload.kind`: the kind-changed guard above parks the item
        found under the OTHER kind, not the one the payload itself
        resolved to. Defaults to `payload.kind`, matching every other
        conflict in this class."""

        async def write() -> IngestOutcome:
            if item is not None:
                item.pdm_sync_state = PdmSyncState.CONFLICT
                kind = item_kind or payload.kind
                if kind == "made" and isinstance(item, MadeItem):
                    await self._made_items.save(item)
                elif kind != "made" and isinstance(item, BoughtItem):
                    await self._bought_items.save(item)
                else:
                    raise TypeError(f"A {kind} conflict cannot park a {type(item).__name__}.")
            await self._upsert_snapshot(
                payload,
                part_number,
                revision,
                item.id if item is not None else None,
                PdmFileSyncState.CONFLICT,
                reason,
                parked_payload=mapped,
                article_name=_mapped_article_name(mapped),
            )
            await self._bus.publish(
                PdmIngestConflict(
                    vault_id=payload.vault_id,
                    file_id=payload.file_id,
                    kind=payload.kind,
                    part_number=part_number,
                    reason=reason,
                )
            )
            return IngestOutcome(
                action="conflict", item_id=item.id if item is not None else None, message=reason
            )

        outcome = await commit_with_number_retry(self._uow, write, attempts=1)
        log.warning(f"PDM ingest {payload.vault_id}/{payload.file_id}: conflict - {reason}")
        return outcome
