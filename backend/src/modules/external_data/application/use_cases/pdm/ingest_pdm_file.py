"""
Applies one PDM file's already-fetched variables to the Glados catalogue.
The rules are documented in docs/reference/pdm-ingest.md (section 2 holds
the numbered rules, sections 3 and 5 the single-transaction guarantee and
PDM releaser attribution) and docs/FIELD_OWNERSHIP.md; the "Rule N" comments
in this package use the numbering of section 2.

Every rule ends by updating the PdmFileSnapshot row for (vault_id, file_id),
and business conditions come back as skipped or conflict outcomes instead
of exceptions. Every write runs inside one write() closure committed through
commit_with_number_retry, with the snapshot upsert in the same transaction;
the made create, made revise and bought create paths fold the reused create
use case's prepare() closure into that same write().

IngestPdmFile runs rules 1 to 4 here and hands the file to the made-item
path (_ingest_made.py) or the bought-item path (_ingest_bought.py). Both
paths are base classes of IngestPdmFile and share the outcome, snapshot and
attribution steps of _ingest_outcome.py, so the whole ingest still runs on
one use case instance with the dependencies its constructor receives.

Two ingests that create or claim the same part number at once both pass
the checks, and the later one's write fails on a numbering constraint at
its commit, which commit_with_number_retry rolls back and reports as
NumberingConflictError. execute() then decides the file once more, now
against what the other ingest committed, so the losing file gets the
outcome the next poll would give it, usually a conflict with the item the
other file created. Should that second decision lose a race too, the file
is parked as a conflict, so a race never escapes as an exception.
"""

import re

from src.modules.catalogue.application.facade.item_commands import CreateBoughtItem
from src.modules.catalogue.application.facade.item_commands import CreateMadeItem
from src.modules.catalogue.application.facade.item_commands import CreateMadeItemRevision
from src.modules.catalogue.application.facade.item_commands import IFabricationMethodRepository
from src.modules.catalogue.application.facade.item_commands import IInspectionMethodRepository
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IPartNumberRegistryCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.pdm_required_fields import is_revision_required
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_skip_reasons import STATE_NOT_WATCHED
from src.modules.external_data.application.services.pdm_variables import map_variables
from src.modules.external_data.application.use_cases.pdm._ingest_bought import BoughtItemIngestion
from src.modules.external_data.application.use_cases.pdm._ingest_made import MadeItemIngestion
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import NumberingConflictError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def _target_status(pdm_settings: AdminPdmSettings, payload: PdmFilePayload) -> str | None:
    """Maps the payload's workflow state onto the linked row's target status, checked against
    the payload's own kind. None means the state is not watched."""
    if payload.state_id in pdm_settings.released_state_ids_for(payload.kind):
        return "active"
    if payload.state_id in pdm_settings.obsolete_state_ids_for(payload.kind):
        return "inactive"
    if payload.state_id in pdm_settings.replaced_state_ids_for(payload.kind):
        return "replaced"
    return None


class IngestPdmFile(MadeItemIngestion, BoughtItemIngestion):
    """Applies one PdmFilePayload. Resolves the system user once (init_db
    seeds exactly one, see IUserRepository) and uses it as the actor for
    every write and every reused create use case; the poller and the
    trigger worker run without a requesting user, so the actor is never a
    parameter of execute(). `session` is the same PdmSessionService every
    other PDM proxy uses, needed here only for
    IPdmGateway.file_transitions (releaser attribution); the file's own
    variables are fetched before this class is ever called."""

    def __init__(
        self,
        made_item_repo: IMadeItemCadStore,
        bought_item_repo: IBoughtItemCadStore,
        article_group_repo: IArticleGroupQueries,
        source_item_repo: ISourceItemQueries,
        supplier_repo: ISupplierQueries,
        fabrication_method_repo: IFabricationMethodRepository,
        inspection_method_repo: IInspectionMethodRepository,
        admin_settings_repo: IExternalDataSettingsRepository,
        snapshot_repo: IPdmFileSnapshotRepository,
        user_repo: IUserRepository,
        user_pdm_link_repo: IUserPdmLinkRepository,
        *,
        create_made_item: CreateMadeItem,
        create_made_item_revision: CreateMadeItemRevision,
        create_bought_item: CreateBoughtItem,
        customer_repo: ICustomerQueries,
        part_number_registry: IPartNumberRegistryCadStore,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        session: PdmSessionService,
    ) -> None:
        self._made_items = made_item_repo
        self._bought_items = bought_item_repo
        self._article_groups = article_group_repo
        self._source_items = source_item_repo
        self._suppliers = supplier_repo
        self._fabrication_methods = fabrication_method_repo
        self._inspection_methods = inspection_method_repo
        self._admin_settings = admin_settings_repo
        self._snapshots = snapshot_repo
        self._user_repo = user_repo
        self._user_pdm_links = user_pdm_link_repo
        self._create_made_item = create_made_item
        self._create_made_item_revision = create_made_item_revision
        self._create_bought_item = create_bought_item
        self._customers = customer_repo
        self._registry = part_number_registry
        self._bus = event_bus
        self._uow = uow
        self._session = session

        # Resolved lazily by _system_actor, since a constructor cannot await
        # the repository; execute() resolves it before anything reads _actor.
        self._actor_cache: User | None = None

    async def _system_actor(self) -> User:
        if self._actor_cache is None:
            actor = await self._user_repo.get_by_username(SYSTEM_USER)
            if actor is None:
                raise RuntimeError(
                    "System user not found; init_db must seed it before PDM ingest can run."
                )
            self._actor_cache = actor
        return self._actor_cache

    async def execute(self, payload: PdmFilePayload) -> IngestOutcome:
        await self._system_actor()
        pdm_settings = await self._admin_settings.get_pdm()
        made_settings = await self._admin_settings.get_made_items()
        order_settings = await self._admin_settings.get_orders()

        variable_map = (
            pdm_settings.made_item_variable_map
            if payload.kind == "made"
            else pdm_settings.bought_item_variable_map
        )
        mapped = map_variables(payload.kind, variable_map, payload.variables)
        part_number = (mapped.get("part_number") or "").strip()
        revision = (mapped.get("revision") or "").strip()

        async def apply() -> IngestOutcome:
            return await self._apply_rules(
                payload,
                mapped,
                part_number,
                revision,
                pdm_settings,
                made_settings,
                order_settings,
            )

        try:
            return await apply()
        except NumberingConflictError:
            # The write is rolled back already; the rollback here also
            # covers a path that let the error out before its own.
            await self._uow.rollback()
            log.info(
                f"PDM ingest {payload.vault_id}/{payload.file_id}: part number "
                f"{part_number} was written by a concurrent ingest; deciding again."
            )
        try:
            return await apply()
        except NumberingConflictError:
            await self._uow.rollback()
            return await self._conflict(
                payload,
                part_number,
                revision or None,
                f"part number {part_number} was written by a concurrent ingest",
                mapped,
            )

    async def _apply_rules(
        self,
        payload: PdmFilePayload,
        mapped: dict[str, str],
        part_number: str,
        revision: str,
        pdm_settings: AdminPdmSettings,
        made_settings: AdminMadeItemSettings,
        order_settings: AdminOrderSettings,
    ) -> IngestOutcome:
        # Rule 1: the workflow state decides the target status, or that this
        # file is not watched at all. Checked first, because a file still being
        # worked on usually has no PDM revision yet, and reporting that as a
        # data problem would be misleading.
        target_status = _target_status(pdm_settings, payload)
        if target_status is None:
            # Keep whichever identity half was read so the files dialog can show it.
            return await self._skip(
                payload, part_number or None, revision or None, STATE_NOT_WATCHED, mapped
            )

        # Rule 2: identity variables must be mapped and non-empty. revision
        # is always required for made items (part of their identity); for
        # bought items, whose identity is the part number alone, it is
        # required only when the admin's configurable selection names it
        # (default on, see is_revision_required).
        if not part_number or (not revision and is_revision_required(payload.kind, pdm_settings)):
            return await self._skip(
                payload, part_number or None, revision or None, "identity variables missing", mapped
            )

        # Rule 3: a file already linked under the other kind must never be
        # re-ingested under this one: the SolidWorks add-in is the first
        # guard (it locks a file's kind once set), this is the backend
        # backstop (docs/reference/pdm-settings.md section 4.3, "kind by datacard").
        other_kind_item = await self._other_kind_link(
            payload.vault_id, payload.file_id, payload.kind
        )
        if other_kind_item is not None:
            other_kind = "bought" if payload.kind == "made" else "made"
            return await self._conflict(
                payload,
                part_number,
                revision,
                f"kind changed, item already linked as {other_kind}",
                mapped,
                item=other_kind_item,
                item_kind=other_kind,
            )

        # Rule 4: the part number must match the kind's external pattern.
        pattern_problem = self._part_number_pattern_problem(
            payload.kind, part_number, made_settings, order_settings
        )
        if pattern_problem is not None:
            return await self._skip(payload, part_number, revision, pattern_problem, mapped)

        if payload.kind == "made":
            return await self._ingest_made(
                payload, mapped, part_number, revision, target_status, made_settings, pdm_settings
            )
        # Bought's revision may legitimately be empty here (see rule 2
        # above); normalized to None so it is stored the same way a
        # revision-less bought item always is, not as "".
        return await self._ingest_bought(
            payload,
            mapped,
            part_number,
            revision or None,
            target_status,
            order_settings,
            pdm_settings,
        )

    @staticmethod
    def _part_number_pattern_problem(
        kind: str,
        part_number: str,
        made_settings: AdminMadeItemSettings,
        order_settings: AdminOrderSettings,
    ) -> str | None:
        """Skip reason when the kind has no external pattern configured or the part number
        does not fully match it."""
        pattern = (
            made_settings.pdm_part_number_pattern
            if kind == "made"
            else order_settings.pdm_part_number_pattern
        )
        if not pattern:
            return (
                f"no external PDM part number pattern configured for {kind} items "
                "(Numbering settings)"
            )
        if not re.fullmatch(pattern, part_number):
            return "part number does not match the configured PDM pattern"
        return None
