"""The bought-item path of PDM ingest, rules 6 to 9 for a bought file.

A released file updates its linked row in place, or, with no linked row
yet, claims the live row carrying the part number, an unclaimed gtin or
order-code match, or else creates a new row; an obsolete or replaced state
is a pure status flip. A row cannot be created or claimed without a
resolved manufacturer. Each of the three writes also applies the file's
EPLAN Data Portal part id under the shadow rule of FIELD_OWNERSHIP
principle 7 and requests the picture of a new link. BoughtItemIngestion is
a base class of IngestPdmFile and reads the dependencies IngestPdmFile's
constructor sets.
"""

from src.modules.catalogue.application.dto.bought_item_dto import CreateBoughtItemCommand
from src.modules.catalogue.application.facade.item_commands import CreateBoughtItem
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import BoughtItemGtinDuplicateError
from src.modules.catalogue.domain.errors import BoughtItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import PartNumberInUseError
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.edp_link import stamp_edp_link
from src.modules.external_data.application.services.pdm_field_resolution import resolve_manufacturer
from src.modules.external_data.application.services.pdm_required_fields import (
    format_missing_required_fields_reason,
)
from src.modules.external_data.application.services.pdm_required_fields import (
    missing_required_fields,
)
from src.modules.external_data.application.services.pdm_variables import parse_edp_part_id
from src.modules.external_data.application.services.pdm_variables import parse_mass
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
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

# BoughtItem fields overwritten verbatim (no coercion) by a claim or an
# in-place update, once mapped. mass, article_group_ids, manufacturer_id
# and revision are handled separately: each needs its own coercion or
# resolution step.
_BOUGHT_VERBATIM_FIELDS: tuple[str, ...] = (
    "article_name",
    "order_code_1",
    "order_code_2",
    "gtin",
    "ean",
    "tariff_number",
    "note",
    "weblink",
)


def _claim_changelog_note(payload: PdmFilePayload, count: int, *, claim_registry: bool) -> str:
    if claim_registry:
        return (
            f"Claimed by PDM file {payload.vault_id}/{payload.file_id}, {count} fields overwritten."
        )
    return (
        f"PDM ingest: linked to PDM file {payload.vault_id}/{payload.file_id}, "
        f"{count} field(s) overwritten."
    )


def _reactivate_bought(item: BoughtItem) -> tuple[int, bool]:
    """Sets the row active and clears a stale successor. Returns the number of fields changed
    and whether the successor was cleared, so the caller can write its changelog line."""
    count = 0
    if item.status != BoughtItemCatalogueStatus.ACTIVE.value:
        item.status = BoughtItemCatalogueStatus.ACTIVE
        count += 1
    successor_cleared = item.successor_item_id is not None
    if successor_cleared:
        item.successor_item_id = None
        count += 1
    return count, successor_cleared


def _bought_create_command(
    mapped: dict[str, str],
    part_number: str,
    manufacturer_id: int,
    article_group_ids: list[int],
) -> CreateBoughtItemCommand:
    return CreateBoughtItemCommand(
        order_code_1=(mapped.get("order_code_1") or "").strip(),
        order_code_2=mapped.get("order_code_2"),
        gtin=mapped.get("gtin"),
        ean=mapped.get("ean"),
        tariff_number=mapped.get("tariff_number"),
        article_name=(mapped.get("article_name") or "").strip(),
        article_group_ids=article_group_ids,
        data_source=DataSource.CAD.value,
        status=BoughtItemCatalogueStatus.ACTIVE.value,
        part_number=part_number,
        mass=parse_mass(mapped.get("mass")),
        note=mapped.get("note"),
        weblink=mapped.get("weblink"),
        manufacturer_id=manufacturer_id,
    )


class BoughtItemIngestion(IngestOutcomeRecorder):
    """IngestPdmFile's bought-item path; see the module docstring."""

    _suppliers: ISupplierQueries
    _create_bought_item: CreateBoughtItem

    async def _ingest_bought(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str | None,
        target_status: str,
        order_settings: AdminOrderSettings,
        pdm_settings: AdminPdmSettings,
    ) -> IngestOutcome:
        existing = await self._bought_items.get_by_pdm_file(payload.vault_id, payload.file_id)

        # PDM owns a linked row's part number (section 5, "Renumbering").
        renumbered_from = _drifted_number(existing, part_number)
        if existing is not None and renumbered_from is not None:
            problem = await self._renumber("bought", [existing], part_number)
            if problem is not None:
                return await self._conflict(
                    payload, part_number, revision, problem, mapped, item=existing
                )

        outcome = await self._apply_bought_rules(
            payload,
            mapped,
            part_number,
            revision,
            target_status,
            pdm_settings,
            existing,
        )
        return _with_renumber_note(outcome, renumbered_from, part_number, existing)

    async def _apply_bought_rules(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str | None,
        target_status: str,
        pdm_settings: AdminPdmSettings,
        existing: BoughtItem | None,
    ) -> IngestOutcome:
        # Rule 6: version guard.
        if existing is not None and _version_guard_applies(existing, target_status, payload):
            return await self._already_applied(payload, part_number, revision, mapped, existing)

        # Rule 7: obsolete/replaced state, a pure status flip, no field
        # remapping, same as the made-item branch.
        if target_status in ("inactive", "replaced"):
            if existing is None:
                reason = _status_flip_without_item_reason(target_status)
                return await self._skip(payload, part_number, revision, reason, mapped)
            return await self._bought_status_transition(
                payload,
                existing,
                part_number,
                revision,
                _mapped_article_name(mapped),
                pdm_settings,
                target_status,
            )

        manufacturer_id, manufacturer_unresolved = await self._resolve_manufacturer(mapped)
        if existing is None:
            # Required to create or claim a row at all.
            if manufacturer_id is None:
                return await self._conflict(
                    payload, part_number, revision, "manufacturer unresolved", mapped
                )
        elif manufacturer_unresolved:
            return await self._conflict(
                payload, part_number, revision, "manufacturer unresolved", mapped, item=existing
            )

        article_group_ids, warning = await self._resolve_article_group_ids(mapped)

        if existing is not None:
            return await self._bought_update_in_place(
                payload,
                mapped,
                part_number,
                revision,
                existing,
                manufacturer_id,
                article_group_ids,
                warning,
            )

        return await self._link_new_bought_row(
            payload,
            mapped,
            part_number,
            revision,
            manufacturer_id,
            article_group_ids,
            warning,
            pdm_settings,
        )

    async def _link_new_bought_row(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str | None,
        manufacturer_id: int | None,
        article_group_ids: list[int],
        warning: str | None,
        pdm_settings: AdminPdmSettings,
    ) -> IngestOutcome:
        """Rule 9 for a file with no linked row yet: claim the live row carrying the part
        number, else claim an unclaimed gtin or order-code match, else create a new row."""
        # Part numbers are unique app-wide and never reused (docs/
        # FIELD_OWNERSHIP.md principle 2): a live row that already carries
        # this part number is by definition the same article, even before
        # any gtin/order-code match. Claiming it here, ahead of
        # find_claim_candidate, avoids the registry conflict _bought_create
        # would otherwise hit trying to claim a number already registered
        # to this very row. get_by_part_number only sees live rows, so an
        # archived row with this number falls through to that same
        # registry conflict on create; not handled specially here.
        by_part_number = await self._bought_items.get_by_part_number(part_number)
        if by_part_number is not None:
            if by_part_number.pdm_file_id is not None:
                # Never the file being ingested: that row would already
                # have been found above as `existing` via get_by_pdm_file.
                return await self._conflict(
                    payload,
                    part_number,
                    revision,
                    f"part number linked to another PDM file (id {by_part_number.pdm_file_id})",
                    mapped,
                    item=by_part_number,
                )
            return await self._bought_claim(
                payload,
                mapped,
                part_number,
                revision,
                by_part_number,
                manufacturer_id,
                article_group_ids,
                warning,
                pdm_settings,
                claim_registry=False,
            )

        candidate = await self._bought_items.find_claim_candidate(
            gtin=mapped.get("gtin") or None,
            manufacturer_id=manufacturer_id,
            order_code_1=mapped.get("order_code_1") or None,
        )
        if candidate is not None:
            return await self._bought_claim(
                payload,
                mapped,
                part_number,
                revision,
                candidate,
                manufacturer_id,
                article_group_ids,
                warning,
                pdm_settings,
            )

        return await self._bought_create(
            payload,
            mapped,
            part_number,
            revision,
            manufacturer_id,
            article_group_ids,
            warning,
            pdm_settings,
        )

    async def _resolve_manufacturer(self, mapped: dict[str, str]) -> tuple[int | None, bool]:
        """Delegates to application.services.pdm_field_resolution.
        resolve_manufacturer, shared with ValidatePdmPayload's own dry run
        of this same check."""
        return await resolve_manufacturer(mapped, self._suppliers)

    async def _bought_create(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str | None,
        manufacturer_id: int | None,
        article_group_ids: list[int],
        warning: str | None,
        pdm_settings: AdminPdmSettings,
    ) -> IngestOutcome:
        assert manufacturer_id is not None  # caller already conflicted otherwise
        if missing := missing_required_fields("bought", mapped, pdm_settings):
            reason = format_missing_required_fields_reason(missing)
            return await self._skip(payload, part_number, revision, reason, mapped)

        attribution = await self._resolve_attribution(
            payload, pdm_settings, "bought", target_status="active"
        )

        cmd = _bought_create_command(mapped, part_number, manufacturer_id, article_group_ids)
        try:
            # prepare() itself already raises BoughtItemGtinDuplicateError
            # for the gtin-duplicate guard (before write() exists at all),
            # so it has to run inside this try too, not just the
            # commit_with_number_retry call below.
            create_write = await self._create_bought_item.prepare(self._actor, cmd)

            async def write() -> IngestOutcome:
                created = await create_write()
                return await self._finish_bought_write_no_commit(
                    payload,
                    mapped,
                    created.id,
                    part_number,
                    revision,
                    "created",
                    f"PDM ingest: created from file {payload.vault_id}/{payload.file_id}.",
                    warning,
                    _mapped_article_name(mapped),
                    pdm_settings,
                    attribution,
                )

            outcome = await commit_with_number_retry(self._uow, write, attempts=1)
        except Exception as exc:
            # See _made_create's matching comment: a conflict raised by
            # CreateBoughtItem's own pre-checks (including the gtin-
            # duplicate check) or its write() closure leaves the merged
            # transaction unfinished, so roll back before recording the
            # conflict or letting anything else propagate.
            await self._uow.rollback()
            if isinstance(
                exc,
                PartNumberInUseError
                | BoughtItemPartNumberDuplicateError
                | BoughtItemGtinDuplicateError,
            ):
                return await self._conflict(payload, part_number, revision, str(exc), mapped)
            raise

        self._log_write_outcome(payload, outcome)
        return outcome

    async def _finish_bought_write_no_commit(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        item_id: int,
        part_number: str,
        revision: str | None,
        action: str,
        changelog_note: str,
        warning: str | None,
        article_name: str | None,
        pdm_settings: AdminPdmSettings,
        attribution: _PdmAttribution,
    ) -> IngestOutcome:
        """Applies the PDM link columns, the Data Portal link, releaser
        attribution, the changelog line and the snapshot upsert to a bought
        item just created, and stages PdmFileIngested, all without
        committing, so
        _bought_create can run this inside the same write() closure as the
        create itself and commit exactly once per ingested file. BoughtItem
        carries no "last changed by" column, so attribution here only
        affects the changelog author name and, when enabled, approver_id."""
        item = await self._bought_items.get_by_id(item_id)
        if item is None:
            raise RuntimeError(f"Bought item #{item_id} vanished immediately after being created.")
        _stamp_pdm_link(item, payload)
        item.revision = revision
        item.changed = now_utc()
        author_name = attribution.author_name or self._actor.full_name
        item.changes = append_changelog(item.changes, author_name, changelog_note)
        edp_relinked = self._apply_edp_part_id(item, mapped, author_name)
        if pdm_settings.set_approver_from_pdm and attribution.resolved_user is not None:
            item.approver_id = attribution.resolved_user.id
        await self._bought_items.save(item)
        await self._request_edp_picture(item, edp_relinked)
        await self._record_ingested(
            payload, "bought", item.id, action, part_number, revision, article_name
        )
        message = _outcome_message(changelog_note, warning, attribution.warning)
        return IngestOutcome(action=action, item_id=item.id, message=message)

    async def _bought_status_transition(
        self,
        payload: PdmFilePayload,
        existing: BoughtItem,
        part_number: str,
        revision: str | None,
        article_name: str | None,
        pdm_settings: AdminPdmSettings,
        target_status: str,
    ) -> IngestOutcome:
        """Same pure status flip as _made_status_transition, see that
        method's docstring."""
        attribution = await self._resolve_attribution(
            payload, pdm_settings, "bought", target_status=target_status
        )
        state_label = "obsolete" if target_status == "inactive" else "replaced"
        old_status = existing.status

        async def write() -> IngestOutcome:
            existing.status = BoughtItemCatalogueStatus(target_status)
            existing.changed = now_utc()
            author_name = attribution.author_name or self._actor.full_name
            existing.changes = append_changelog(
                existing.changes,
                author_name,
                f"PDM ingest: file moved to {state_label} state {payload.state!r}; "
                f"status changed from {old_status!r} to {target_status!r}.",
            )
            if target_status == "inactive" and existing.successor_item_id is not None:
                existing.successor_item_id = None
                existing.changes = append_changelog(
                    existing.changes, author_name, _successor_cleared_note(payload)
                )
            _stamp_pdm_link(existing, payload)
            if pdm_settings.set_approver_from_pdm and attribution.resolved_user is not None:
                existing.approver_id = attribution.resolved_user.id
            await self._bought_items.save(existing)
            await self._record_ingested(
                payload, "bought", existing.id, "status", part_number, revision, article_name
            )
            message = _outcome_message(
                f"Status changed from {old_status!r} to {target_status!r} "
                f"(PDM {state_label} state).",
                attribution.warning,
            )
            return IngestOutcome(action="status", item_id=existing.id, message=message)

        return await commit_with_number_retry(self._uow, write, attempts=1)

    async def _bought_update_in_place(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str | None,
        existing: BoughtItem,
        manufacturer_id: int | None,
        article_group_ids: list[int],
        warning: str | None,
    ) -> IngestOutcome:
        async def write() -> IngestOutcome:
            count = self._apply_bought_mapped_fields(
                existing, mapped, manufacturer_id, article_group_ids
            )
            edp_relinked = self._apply_edp_part_id(existing, mapped, self._actor.full_name)
            count += int(edp_relinked)
            # Lifecycle status follows PDM's own workflow state, same reasoning as
            # _apply_made_in_place_fields.
            status_count, successor_cleared = _reactivate_bought(existing)
            count += status_count
            if successor_cleared:
                existing.changes = append_changelog(
                    existing.changes, self._actor.full_name, _successor_cleared_note(payload)
                )

            if count:
                existing.changed = now_utc()
                existing.changes = append_changelog(
                    existing.changes,
                    self._actor.full_name,
                    f"PDM ingest: updated from file {payload.vault_id}/{payload.file_id}, "
                    f"{count} field(s) overwritten.",
                )
            _stamp_pdm_link(existing, payload)
            await self._bought_items.save(existing)
            await self._request_edp_picture(existing, edp_relinked)
            await self._record_ingested(
                payload,
                "bought",
                existing.id,
                "updated",
                part_number,
                revision,
                _mapped_article_name(mapped),
            )
            message = _outcome_message(f"Updated {count} field(s).", warning)
            return IngestOutcome(action="updated", item_id=existing.id, message=message)

        return await commit_with_number_retry(self._uow, write, attempts=1)

    async def _bought_claim(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str | None,
        candidate: BoughtItem,
        manufacturer_id: int | None,
        article_group_ids: list[int],
        warning: str | None,
        pdm_settings: AdminPdmSettings,
        *,
        claim_registry: bool = True,
    ) -> IngestOutcome:
        """Claims `candidate` for this PDM file: overwrites its mapped
        fields, sets the link columns and records a changelog line.
        `claim_registry` is False only for _ingest_bought's part-number-
        match branch, where `candidate.part_number` already equals
        `part_number` and is already registered to this very row,
        claiming it again would raise PartNumberInUseError against
        itself, and releasing the "old" number would release the number
        this row keeps."""
        if missing := missing_required_fields("bought", mapped, pdm_settings):
            reason = format_missing_required_fields_reason(missing)
            return await self._skip(payload, part_number, revision, reason, mapped)

        attribution = await self._resolve_attribution(
            payload, pdm_settings, "bought", target_status="active"
        )
        old_number = candidate.part_number

        async def write() -> IngestOutcome:
            if claim_registry:
                await self._registry.claim(part_number, "bought")  # may raise PartNumberInUseError
                candidate.part_number = part_number

            candidate.data_source = DataSource.CAD
            count = self._apply_bought_mapped_fields(
                candidate, mapped, manufacturer_id, article_group_ids
            )
            author_name = attribution.author_name or self._actor.full_name
            edp_relinked = self._apply_edp_part_id(candidate, mapped, author_name)
            count += int(edp_relinked)
            # Lifecycle status follows PDM's own workflow state, same reasoning as
            # _apply_made_in_place_fields: a claimed row may already carry a stale status or
            # successor from before it was PDM-linked.
            status_count, successor_cleared = _reactivate_bought(candidate)
            count += status_count

            if claim_registry and old_number is not None:
                await self._registry.release_if_unused(old_number)

            changelog_note = _claim_changelog_note(payload, count, claim_registry=claim_registry)
            candidate.changed = now_utc()
            candidate.changes = append_changelog(candidate.changes, author_name, changelog_note)
            if successor_cleared:
                candidate.changes = append_changelog(
                    candidate.changes, author_name, _successor_cleared_note(payload)
                )
            _stamp_pdm_link(candidate, payload)
            if pdm_settings.set_approver_from_pdm and attribution.resolved_user is not None:
                candidate.approver_id = attribution.resolved_user.id
            await self._bought_items.save(candidate)
            await self._request_edp_picture(candidate, edp_relinked)
            await self._record_ingested(
                payload,
                "bought",
                candidate.id,
                "claimed",
                part_number,
                revision,
                _mapped_article_name(mapped),
            )
            message = _outcome_message(changelog_note, warning, attribution.warning)
            return IngestOutcome(action="claimed", item_id=candidate.id, message=message)

        try:
            return await commit_with_number_retry(self._uow, write, attempts=1)
        except PartNumberInUseError as exc:
            # claim() raises before anything in write() is persisted, so
            # nothing from this attempt was committed.
            return await self._conflict(
                payload, part_number, revision, str(exc), mapped, item=candidate
            )

    def _apply_edp_part_id(self, item: BoughtItem, mapped: dict[str, str], author: str) -> bool:
        """The shadow rule of FIELD_OWNERSHIP principle 7 for edp_part_id:
        the file's part id replaces the item's link only when it differs
        from the one PDM sent last time, so a link made in the web survives
        every sync of an unchanged file. Returns whether the link changed."""
        if "edp_part_id" not in mapped:
            return False
        part_id = parse_edp_part_id(mapped["edp_part_id"])
        if part_id == item.pdm_edp_part_id:
            return False
        item.pdm_edp_part_id = part_id
        if part_id == item.edp_part_id:
            return False
        stamp_edp_link(item, author, part_id)
        return True

    async def _request_edp_picture(self, item: BoughtItem, relinked: bool) -> None:
        """Stages the picture request for a changed link, in the same
        transaction as the write that made it. An unlink is a change too:
        the worker then removes the portal picture."""
        if relinked:
            await self._bus.publish(BoughtItemEdpPictureRequested(item_id=item.id))

    def _apply_bought_mapped_fields(
        self,
        item: BoughtItem,
        mapped: dict[str, str],
        manufacturer_id: int | None,
        article_group_ids: list[int],
    ) -> int:
        count = 0
        for field in _BOUGHT_VERBATIM_FIELDS:
            if field in mapped:
                setattr(item, field, mapped[field])
                count += 1
        if "mass" in mapped:
            item.mass = parse_mass(mapped["mass"])
            count += 1
        if "article_group_ids" in mapped:
            item.article_group_ids = article_group_ids
            count += 1
        if "manufacturer_id" in mapped and manufacturer_id is not None:
            item.manufacturer_id = manufacturer_id
            count += 1
        if "revision" in mapped:
            # "" means "no revision on the card", stored the same way a
            # never-linked bought item's revision is (see is_revision_required).
            item.revision = mapped["revision"] or None
            count += 1
        return count
