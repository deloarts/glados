"""The made-item path of PDM ingest, rules 6 to 8 for a made file.

A released file creates the item, revises its family when the revision
differs, or updates the newest revision in place under the admin's
revision field policy; an obsolete or replaced state is a pure status flip.
The create and revise branches fold the reused create use case's prepare()
closure into one write() with the snapshot upsert, so each file commits
once. MadeItemIngestion is a base class of IngestPdmFile and reads the
dependencies IngestPdmFile's constructor sets.
"""

from dataclasses import dataclass

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemRevisionCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionItemCommand
from src.modules.catalogue.application.facade.item_commands import CreateMadeItem
from src.modules.catalogue.application.facade.item_commands import CreateMadeItemRevision
from src.modules.catalogue.application.facade.item_commands import IFabricationMethodRepository
from src.modules.catalogue.application.facade.item_commands import IInspectionMethodRepository
from src.modules.catalogue.application.facade.item_commands import build_and_save_processes
from src.modules.catalogue.application.facade.item_commands import validate_processes
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import PartNumberInUseError
from src.modules.catalogue.domain.policies.item_field_ownership import REVISION_POLICY_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.pdm_required_fields import (
    format_missing_required_fields_reason,
)
from src.modules.external_data.application.services.pdm_required_fields import (
    missing_required_fields,
)
from src.modules.external_data.application.services.pdm_variables import parse_date
from src.modules.external_data.application.services.pdm_variables import parse_mass
from src.modules.external_data.application.services.pdm_variables import parse_processes
from src.modules.external_data.application.services.pdm_variables import process_entry_missing_role
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import (
    IngestOutcomeRecorder,
)
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import _drifted_number
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import _mapped_article_name
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import _outcome_message
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import _PdmAttribution
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import _stamp_pdm_link
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import (
    _status_flip_without_item_reason,
)
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import (
    _successor_cleared_note,
)
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import (
    _version_guard_applies,
)
from src.modules.external_data.application.use_cases.pdm._ingest_outcome import _with_renumber_note
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

# Fields the generic in-place loop applies directly from `mapped`; every
# other REVISION_POLICY_FIELDS entry has its own mechanism:
# source_item_id is the §1.7 shadow rule (always evaluated, independent of
# the policy flag), processes is a whole-routing replace behind its own
# policy check.
_GENERIC_IN_PLACE_FIELDS: tuple[str, ...] = tuple(
    f for f in REVISION_POLICY_FIELDS if f not in ("source_item_id", "processes")
)


@dataclass
class _MadeResolved:
    """Reference/list fields shared by the made create, revise and
    in-place-update branches, resolved once per file so the three don't
    repeat the same lookups."""

    article_group_ids: list[int]
    bought_item_id: int | None
    source_item_id: int | None
    # Archived customers resolve too; only a dangling id becomes None.
    customer_id: int | None
    warning: str | None


def _merged_pdm_update_in_place_policy(settings: AdminMadeItemSettings) -> dict[str, bool]:
    """default_policy()'s pdm_update_in_place flags, overridden per field
    by whatever the admin has stored: a field missing from the stored
    list (e.g. after a schema change) keeps the default rather than being
    treated as False."""
    merged = {p.field: p.pdm_update_in_place for p in default_policy()}
    merged.update({p.field: p.pdm_update_in_place for p in settings.revision_field_policy})
    return merged


def _parse_made_processes(
    mapped: dict[str, str], pdm_settings: AdminPdmSettings
) -> tuple[list[CreateMadeItemProcessCommand], str | None]:
    """Parses the routing for a made create or revise and returns the skip reason when a
    process entry has no role or a required field is missing."""
    if process_entry_missing_role(mapped.get("processes")):
        return [], "process entry without role"
    processes = parse_processes(mapped.get("processes"))
    missing = missing_required_fields("made", mapped, pdm_settings, processes)
    if missing:
        return processes, format_missing_required_fields_reason(missing)
    return processes, None


def _made_create_command(
    mapped: dict[str, str],
    part_number: str,
    revision: str,
    resolved: _MadeResolved,
    processes: list[CreateMadeItemProcessCommand],
    attribution: _PdmAttribution,
) -> CreateMadeItemCommand:
    return CreateMadeItemCommand(
        revision=revision,
        revision_date=parse_date(mapped.get("revision_date")) or attribution.transition_date,
        revision_note=mapped.get("revision_note") or attribution.transition_comment,
        article_name=(mapped.get("article_name") or "").strip(),
        article_group_ids=resolved.article_group_ids,
        data_source=DataSource.CAD.value,
        status=MadeItemCatalogueStatus.ACTIVE.value,
        part_number=part_number,
        material=mapped.get("material"),
        mass=parse_mass(mapped.get("mass")),
        base_size=mapped.get("base_size"),
        note=mapped.get("note"),
        weblink=mapped.get("weblink"),
        bought_item_id=resolved.bought_item_id,
        source_item_id=resolved.source_item_id,
        customer_id=resolved.customer_id,
        customer_part_number=mapped.get("customer_part_number"),
        customer_revision=mapped.get("customer_revision"),
        processes=processes,
    )


def _made_revision_command(
    mapped: dict[str, str],
    revision: str,
    newest: MadeItem,
    made_settings: AdminMadeItemSettings,
    resolved: _MadeResolved,
    processes: list[CreateMadeItemProcessCommand],
    attribution: _PdmAttribution,
) -> CreateMadeItemRevisionCommand:
    return CreateMadeItemRevisionCommand(
        predecessor_status=made_settings.revision_predecessor_status_pdm,
        item=MadeItemRevisionItemCommand(
            revision_date=(parse_date(mapped.get("revision_date")) or attribution.transition_date),
            revision_note=mapped.get("revision_note") or attribution.transition_comment,
            article_name=mapped.get("article_name") or newest.article_name,
            article_group_ids=resolved.article_group_ids,
            material=mapped.get("material"),
            mass=parse_mass(mapped.get("mass")),
            base_size=mapped.get("base_size"),
            note=mapped.get("note"),
            weblink=mapped.get("weblink"),
            bought_item_id=resolved.bought_item_id,
            source_item_id=resolved.source_item_id,
            customer_id=resolved.customer_id,
            customer_part_number=mapped.get("customer_part_number"),
            customer_revision=mapped.get("customer_revision"),
            processes=processes,
        ),
        revision=revision,
        data_source=DataSource.CAD.value,
    )


class MadeItemIngestion(IngestOutcomeRecorder):
    """IngestPdmFile's made-item path; see the module docstring."""

    _source_items: ISourceItemQueries
    _customers: ICustomerQueries
    _fabrication_methods: IFabricationMethodRepository
    _inspection_methods: IInspectionMethodRepository
    _create_made_item: CreateMadeItem
    _create_made_item_revision: CreateMadeItemRevision

    async def _ingest_made(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str,
        target_status: str,
        made_settings: AdminMadeItemSettings,
        pdm_settings: AdminPdmSettings,
    ) -> IngestOutcome:
        family = await self._made_items.get_family_by_pdm_file(payload.vault_id, payload.file_id)
        newest = family[0] if family else None

        # PDM owns a linked row's part number (section 5, "Renumbering").
        renumbered_from = _drifted_number(newest, part_number)
        if newest is not None and renumbered_from is not None:
            problem = await self._renumber("made", family, part_number)
            if problem is not None:
                return await self._conflict(
                    payload, part_number, revision, problem, mapped, item=newest
                )

        outcome = await self._apply_made_rules(
            payload,
            mapped,
            part_number,
            revision,
            target_status,
            made_settings,
            pdm_settings,
            newest,
        )
        return _with_renumber_note(outcome, renumbered_from, part_number, newest)

    async def _apply_made_rules(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str,
        target_status: str,
        made_settings: AdminMadeItemSettings,
        pdm_settings: AdminPdmSettings,
        newest: MadeItem | None,
    ) -> IngestOutcome:
        # Rule 6: version guard.
        if newest is not None and _version_guard_applies(newest, target_status, payload):
            return await self._already_applied(payload, part_number, revision, mapped, newest)

        # Rule 7: obsolete/replaced state, a pure status flip, no field
        # remapping. Skipped when the payload's own kind has never linked a
        # row for this file.
        if target_status in ("inactive", "replaced"):
            if newest is None:
                reason = _status_flip_without_item_reason(target_status)
                return await self._skip(payload, part_number, revision, reason, mapped)
            return await self._made_status_transition(
                payload,
                newest,
                part_number,
                revision,
                _mapped_article_name(mapped),
                pdm_settings,
                target_status,
            )

        resolved = await self._resolve_made_fields(mapped)

        # Rule 8: made, no row -> create.
        if newest is None:
            return await self._made_create(
                payload, mapped, part_number, revision, resolved, pdm_settings
            )

        # Rule 8: made, family exists, revision differs -> new revision.
        if revision != newest.revision:
            return await self._made_revise(
                payload,
                mapped,
                part_number,
                revision,
                newest,
                made_settings,
                resolved,
                pdm_settings,
            )

        # Rule 8: made, family exists, same revision -> in-place update.
        return await self._made_update_in_place(
            payload, mapped, part_number, revision, newest, made_settings, resolved
        )

    async def _resolve_made_fields(self, mapped: dict[str, str]) -> _MadeResolved:
        article_group_ids, warning = await self._resolve_article_group_ids(mapped)
        return _MadeResolved(
            article_group_ids=article_group_ids,
            bought_item_id=await self._resolve_existing_id(
                mapped, "bought_item_id", self._bought_items.get_by_id
            ),
            source_item_id=await self._resolve_existing_id(
                mapped, "source_item_id", self._source_items.get_by_id
            ),
            customer_id=await self._resolve_existing_id(
                mapped, "customer_id", self._customers.get_by_id
            ),
            warning=warning,
        )

    async def _made_create(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str,
        resolved: _MadeResolved,
        pdm_settings: AdminPdmSettings,
    ) -> IngestOutcome:
        processes, problem = _parse_made_processes(mapped, pdm_settings)
        if problem is not None:
            return await self._skip(payload, part_number, revision, problem, mapped)

        attribution = await self._resolve_attribution(
            payload, pdm_settings, "made", target_status="active"
        )

        cmd = _made_create_command(mapped, part_number, revision, resolved, processes, attribution)
        try:
            # prepare() itself never raises these for CreateMadeItem (both
            # the registry claim and the duplicate guard live inside its
            # write() closure), but it is covered here too so the try
            # keeps catching whichever phase they end up raised from.
            create_write = await self._create_made_item.prepare(self._actor, cmd)

            async def write() -> IngestOutcome:
                created = await create_write()
                return await self._finish_made_write_no_commit(
                    payload,
                    created.id,
                    part_number,
                    revision,
                    "created",
                    f"PDM ingest: created from file {payload.vault_id}/{payload.file_id}.",
                    resolved.source_item_id,
                    resolved.warning,
                    _mapped_article_name(mapped),
                    pdm_settings,
                    attribution,
                )

            outcome = await commit_with_number_retry(self._uow, write, attempts=1)
        except Exception as exc:
            # A conflict raised by CreateMadeItem's own pre-checks or its
            # write() closure (registry claim, duplicate guard) leaves the
            # merged transaction unfinished; roll back before either
            # recording the conflict or letting anything else propagate, so
            # _conflict's own commit never picks up stray pending state
            # from this aborted attempt.
            await self._uow.rollback()
            if isinstance(exc, PartNumberInUseError | MadeItemPartNumberDuplicateError):
                return await self._conflict(payload, part_number, revision, str(exc), mapped)
            raise

        self._log_write_outcome(payload, outcome)
        return outcome

    async def _made_revise(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str,
        newest: MadeItem,
        made_settings: AdminMadeItemSettings,
        resolved: _MadeResolved,
        pdm_settings: AdminPdmSettings,
    ) -> IngestOutcome:
        processes, problem = _parse_made_processes(mapped, pdm_settings)
        if problem is not None:
            return await self._skip(payload, part_number, revision, problem, mapped)

        attribution = await self._resolve_attribution(
            payload, pdm_settings, "made", target_status="active"
        )

        cmd = _made_revision_command(
            mapped, revision, newest, made_settings, resolved, processes, attribution
        )
        try:
            # prepare() itself already raises MadeItemPartNumberDuplicateError
            # for the revision-collision guard (before write() exists at
            # all), so it has to run inside this try too, not just the
            # commit_with_number_retry call below.
            prepared = await self._create_made_item_revision.prepare(self._actor, newest.id, cmd)

            async def write() -> IngestOutcome:
                revised = await prepared.write()
                return await self._finish_made_write_no_commit(
                    payload,
                    revised.id,
                    part_number,
                    revision,
                    "revised",
                    f"PDM ingest: revised to {revision!r} from file {payload.vault_id}/"
                    f"{payload.file_id}.",
                    resolved.source_item_id,
                    resolved.warning,
                    _mapped_article_name(mapped),
                    pdm_settings,
                    attribution,
                )

            outcome = await commit_with_number_retry(self._uow, write, attempts=1)
        except Exception as exc:
            # See _made_create's matching comment: a conflict raised by
            # CreateMadeItemRevision's own pre-checks or its write() closure
            # leaves the merged transaction unfinished, so roll back before
            # recording the conflict or letting anything else propagate.
            await self._uow.rollback()
            if isinstance(exc, PartNumberInUseError | MadeItemPartNumberDuplicateError):
                return await self._conflict(
                    payload, part_number, revision, str(exc), mapped, item=newest
                )
            raise

        self._log_write_outcome(payload, outcome)
        return outcome

    async def _finish_made_write_no_commit(
        self,
        payload: PdmFilePayload,
        item_id: int,
        part_number: str,
        revision: str,
        action: str,
        changelog_note: str,
        source_item_id: int | None,
        warning: str | None,
        article_name: str | None,
        pdm_settings: AdminPdmSettings,
        attribution: _PdmAttribution,
    ) -> IngestOutcome:
        """Applies the PDM link columns, the §1.7 shadow seed, releaser
        attribution, the changelog line and the snapshot upsert to a made
        item just created or revised, and stages PdmFileIngested, all
        without committing, so _made_create and _made_revise can run this
        inside the same write() closure as the create/revise itself and
        commit exactly once per ingested file. Re-fetches the item by id
        rather than reusing the entity CreateMadeItem/CreateMadeItemRevision
        returned, since it is the same session and sees the row already
        flushed there."""
        item = await self._made_items.get_by_id(item_id)
        if item is None:
            raise RuntimeError(f"Made item #{item_id} vanished immediately after being created.")
        _stamp_pdm_link(item, payload)
        item.pdm_source_item_id = source_item_id
        item.changed = now_utc()
        item.changed_by_id = (
            attribution.resolved_user.id
            if attribution.resolved_user is not None
            else self._actor.id
        )
        author_name = attribution.author_name or self._actor.full_name
        item.changes = append_changelog(item.changes, author_name, changelog_note)
        if pdm_settings.set_approver_from_pdm and attribution.resolved_user is not None:
            item.approver_id = attribution.resolved_user.id
        await self._made_items.save(item)
        await self._record_ingested(
            payload, "made", item.id, action, part_number, revision, article_name
        )
        message = _outcome_message(changelog_note, warning, attribution.warning)
        return IngestOutcome(action=action, item_id=item.id, message=message)

    async def _made_status_transition(
        self,
        payload: PdmFilePayload,
        newest: MadeItem,
        part_number: str,
        revision: str,
        article_name: str | None,
        pdm_settings: AdminPdmSettings,
        target_status: str,
    ) -> IngestOutcome:
        """A pure status flip, called for a workflow state landing in the
        kind's own obsolete (`target_status="inactive"`) or replaced
        (`target_status="replaced"`) list, no field remapping; see rule
        7. A stale `successor_item_id` is cleared when the new status is
        `inactive` (the row is no longer superseded); a `replaced` target
        leaves it untouched, PDM carries no successor reference of its
        own (docs/reference/field-ownership.md section 4)."""
        attribution = await self._resolve_attribution(
            payload, pdm_settings, "made", target_status=target_status
        )
        state_label = "obsolete" if target_status == "inactive" else "replaced"
        old_status = newest.status

        async def write() -> IngestOutcome:
            newest.status = MadeItemCatalogueStatus(target_status)
            newest.changed = now_utc()
            newest.changed_by_id = (
                attribution.resolved_user.id
                if attribution.resolved_user is not None
                else self._actor.id
            )
            author_name = attribution.author_name or self._actor.full_name
            newest.changes = append_changelog(
                newest.changes,
                author_name,
                f"PDM ingest: file moved to {state_label} state {payload.state!r}; "
                f"status changed from {old_status!r} to {target_status!r}.",
            )
            if target_status == "inactive" and newest.successor_item_id is not None:
                newest.successor_item_id = None
                newest.changes = append_changelog(
                    newest.changes, author_name, _successor_cleared_note(payload)
                )
            _stamp_pdm_link(newest, payload)
            if pdm_settings.set_approver_from_pdm and attribution.resolved_user is not None:
                newest.approver_id = attribution.resolved_user.id
            await self._made_items.save(newest)
            await self._record_ingested(
                payload, "made", newest.id, "status", part_number, revision, article_name
            )
            message = _outcome_message(
                f"Status changed from {old_status!r} to {target_status!r} "
                f"(PDM {state_label} state).",
                attribution.warning,
            )
            return IngestOutcome(action="status", item_id=newest.id, message=message)

        return await commit_with_number_retry(self._uow, write, attempts=1)

    async def _made_update_in_place(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str,
        newest: MadeItem,
        made_settings: AdminMadeItemSettings,
        resolved: _MadeResolved,
    ) -> IngestOutcome:
        async def write() -> IngestOutcome:
            changed_fields = self._apply_made_in_place_fields(
                newest, payload, mapped, resolved, made_settings
            )
            policy = _merged_pdm_update_in_place_policy(made_settings)
            if policy.get("processes", False) and "processes" in mapped:
                steps = parse_processes(mapped["processes"])
                await self._replace_processes(newest.id, steps)
                changed_fields.append("processes")

            _stamp_pdm_link(newest, payload)
            if changed_fields:
                newest.changed = now_utc()
                newest.changed_by_id = self._actor.id
                newest.changes = append_changelog(
                    newest.changes,
                    self._actor.full_name,
                    f"PDM ingest: updated {', '.join(changed_fields)} from file "
                    f"{payload.vault_id}/{payload.file_id}.",
                )
            await self._made_items.save(newest)
            await self._upsert_snapshot(
                payload,
                part_number,
                revision,
                newest.id,
                PdmFileSyncState.INGESTED,
                None,
                article_name=_mapped_article_name(mapped),
            )

            if changed_fields:
                action = "updated"
                message = f"Updated {', '.join(changed_fields)}."
                await self._publish_ingested(
                    payload, "made", newest.id, action, part_number, revision
                )
            else:
                action = "skipped"
                message = "no in-place changes"
            message = _outcome_message(message, resolved.warning)
            return IngestOutcome(action=action, item_id=newest.id, message=message)

        return await commit_with_number_retry(self._uow, write, attempts=1)

    def _apply_made_in_place_fields(
        self,
        newest: MadeItem,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        resolved: _MadeResolved,
        made_settings: AdminMadeItemSettings,
    ) -> list[str]:
        """Overwrites the policy-flagged fields that actually changed, reactivates the row and
        applies the source_item_id shadow rule. Returns the changed field names in order."""
        policy = _merged_pdm_update_in_place_policy(made_settings)
        changed_fields: list[str] = []

        for field in _GENERIC_IN_PLACE_FIELDS:
            if not policy.get(field, False) or field not in mapped:
                continue
            new_value = self._in_place_value(field, mapped, resolved)
            if getattr(newest, field) != new_value:
                setattr(newest, field, new_value)
                changed_fields.append(field)

        # This path is only reached for a released state, so lifecycle status follows PDM to
        # "active": a row left inactive or replaced without a revision bump is reactivated, and
        # a stale successor is cleared with its own changelog line.
        if newest.status != MadeItemCatalogueStatus.ACTIVE.value:
            newest.status = MadeItemCatalogueStatus.ACTIVE
            changed_fields.append("status")
        if newest.successor_item_id is not None:
            newest.successor_item_id = None
            changed_fields.append("successor_item_id")
            newest.changes = append_changelog(
                newest.changes, self._actor.full_name, _successor_cleared_note(payload)
            )

        # Shadow rule (FIELD_OWNERSHIP principle 7): independent of the policy flag, and applied
        # only when the CAD value itself moved since the last sync, so a web edit survives a
        # resync of an unchanged CAD value.
        if "source_item_id" in mapped and resolved.source_item_id != newest.pdm_source_item_id:
            newest.source_item_id = resolved.source_item_id
            newest.pdm_source_item_id = resolved.source_item_id
            changed_fields.append("source_item_id")
        return changed_fields

    def _in_place_value(
        self, field: str, mapped: dict[str, str], resolved: _MadeResolved
    ) -> object:
        if field == "mass":
            return parse_mass(mapped[field])
        if field == "revision_date":
            return parse_date(mapped[field])
        if field == "article_group_ids":
            return resolved.article_group_ids
        if field == "bought_item_id":
            return resolved.bought_item_id
        if field == "customer_id":
            return resolved.customer_id
        return mapped[field]

    async def _replace_processes(
        self, made_item_id: int, steps: list[CreateMadeItemProcessCommand]
    ) -> None:
        """Whole-routing replace for the (default-off) "processes:
        update in place" policy: revalidates the freshly parsed steps the
        same way CreateMadeItem does, then swaps them in."""
        inspection_methods_by_id = await validate_processes(
            steps, self._fabrication_methods, self._inspection_methods
        )
        for process in await self._made_items.get_processes(made_item_id):
            await self._made_items.delete_process(process)
        await build_and_save_processes(
            self._made_items,
            made_item_id,
            steps,
            inspection_methods_by_id,
            self._actor.id,
            now_utc(),
        )
