"""
Validate and commit a batch of made item demand rows parsed from a
user-uploaded Excel sheet on the frontend, through the batch use cases the
demand families share (_demand_family/batch_demands.py). This module holds
the made item row resolver and the demand a row creates.

Lookup-only importer: a row's catalogue item is *found*, never created or
updated (see docs/reference/field-ownership.md section 1: batch paths must never author
item data). Divergence between the file and the matched catalogue item's
article name is reported as a warning only and never applied. A row whose
project is not active, or whose item new work may not name (not active,
archived or missing in PDM), is invalid, since the demand it would create is
refused.

Unlike the bought importer, made items have no second natural key to fall
back on (no order code / manufacturer): the only lookup key is part number
+ revision, both required, matched exactly (normalized) against non-deleted
items. A row with a part number but no revision is 'invalid', not narrowed
to a part-number-only match.
"""

from typing import Literal

from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemInactiveError
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemCreated
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
from src.modules.fulfillment.application.dto.made_item_demand_dto import (
    CommitBatchMadeItemDemandsResult,
)
from src.modules.fulfillment.application.dto.made_item_demand_dto import FieldDivergence
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemBatchDemandRowInput
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemRowValidationResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import (
    ValidateBatchMadeItemDemandsResult,
)
from src.modules.fulfillment.application.services.batch_demand_import import ItemLookupStatus
from src.modules.fulfillment.application.services.batch_demand_import import decide_row_status
from src.modules.fulfillment.application.services.batch_demand_import import new_demand_refusals
from src.modules.fulfillment.application.services.batch_demand_import import quantity_error
from src.modules.fulfillment.application.services.batch_demand_import import resolve_project
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.batch_demands import (
    CommitBatchDemands,
)
from src.modules.fulfillment.application.use_cases._demand_family.batch_demands import (
    ValidateBatchDemands,
)
from src.modules.fulfillment.application.use_cases.made_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.services.made_item_demand_rules import MadeItemDemandRules
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.platform.application.services.import_text import norm
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

_MatchSource = Literal["part_number_revision"]

# Fixed unit for made-item demands: there is no unit column in the batch
# sheet and nothing to import, since every made-item demand is counted in
# pieces. See src/modules/fulfillment/application/dto/made_item_demand_dto.py's batch section.
_MADE_ITEM_DEMAND_UNIT = "PCS"


class _RowResolver:
    """Shared row-resolution logic used by both validate (read-only) and
    commit (re-validates from scratch before writing, never trusts
    client-cached validation state, since DB data may have changed since
    the user last clicked Validate).

    Lookup: part number AND revision, both required, exact/normalized
    against non-deleted items. No fallback of any kind: unlike the bought
    resolver there is no second natural key. Duplicate matches block the
    row as 'ambiguous' rather than narrowing further."""

    def __init__(
        self,
        item_repo: IMadeItemQueries,
        project_repo: IProjectQueries,
    ) -> None:
        self._items = item_repo
        self._projects = project_repo

    async def resolve(self, row: MadeItemBatchDemandRowInput) -> MadeItemRowValidationResult:
        errors: list[str] = []

        if not row.project_number or not row.project_number.strip():
            errors.append("Project number is required.")
        if quantity := quantity_error(row.quantity):
            errors.append(quantity)
        if not row.part_number or not row.part_number.strip():
            errors.append("Part number is required.")
        if not row.revision or not row.revision.strip():
            errors.append("Revision is required.")

        if errors:
            return MadeItemRowValidationResult(
                row_index=row.row_index, row_status="invalid", errors=errors
            )

        # Project resolution is attempted regardless of the item-lookup outcome,
        # so the UI can surface a missing-project error alongside a missing-item
        # one. row_status precedence: a malformed row is invalid (above), then
        # unresolved_reference > ambiguous > not_found; a row that resolves but
        # whose demand would be refused is invalid; otherwise matched.
        exact_project, project_error = await resolve_project(self._projects, row.project_number)

        assert row.part_number is not None
        assert row.revision is not None
        item_status, matched, item_errors = await self._lookup_by_part_number_and_revision(
            row.part_number, row.revision
        )
        match_source: _MatchSource | None = (
            "part_number_revision" if item_status == "matched" else None
        )
        refusals = new_demand_refusals(
            exact_project,
            matched,
            assert_item_demandable=MadeItemCatalogueRules.assert_item_demandable,
            item_error=MadeItemInactiveError,
        )
        row_status, row_errors = decide_row_status(
            project_error, item_status, item_errors, refusals
        )

        divergences = self._divergences(row, matched) if row_status == "matched" else []

        return MadeItemRowValidationResult(
            row_index=row.row_index,
            row_status=row_status,
            match_source=match_source,
            matched_item=MadeItemMapper.to_result(matched) if matched else None,
            divergences=divergences,
            resolved_project_id=exact_project.id if exact_project else None,
            errors=row_errors,
        )

    async def _lookup_by_part_number_and_revision(
        self, part_number: str, revision: str
    ) -> tuple[ItemLookupStatus, MadeItem | None, list[str]]:
        # Strip before it hits the repo's substring (ILIKE '%term%') prefilter:
        # incidental surrounding whitespace in the uploaded cell must not make
        # the prefilter miss a value that is an exact match once normalized.
        # The repo prefilter pages at DEFAULT_PAGE_SIZE, so a short value could
        # push the exact match off the first page; ask for the largest page
        # the repo allows.
        _, candidates = await self._items.get_multi(
            MadeItemFilterDto(part_number=part_number.strip(), limit=MAX_PAGE_SIZE)
        )
        exact = [
            i
            for i in candidates
            if not i.archived
            and norm(i.part_number) == norm(part_number)
            and norm(i.revision) == norm(revision)
        ]
        if len(exact) > 1:
            return (
                "ambiguous",
                None,
                [
                    f"Multiple catalogue items share part number {part_number!r} "
                    f"revision {revision!r}."
                ],
            )
        if len(exact) == 1:
            return "matched", exact[0], []
        return (
            "not_found",
            None,
            [f"No catalogue item found for part number {part_number!r} revision {revision!r}."],
        )

    def _divergences(
        self,
        row: MadeItemBatchDemandRowInput,
        matched: MadeItem | None,
    ) -> list[FieldDivergence]:
        if matched is None:
            return []

        divergences: list[FieldDivergence] = []

        if row.article_name and norm(row.article_name) != norm(matched.article_name):
            divergences.append(
                FieldDivergence(
                    field="article_name", db_value=matched.article_name, file_value=row.article_name
                )
            )

        return divergences


class ValidateBatchMadeItemDemandRows(
    ValidateBatchDemands[
        MadeItemDemandItem,
        MadeItemBatchDemandRowInput,
        MadeItemRowValidationResult,
        ValidateBatchMadeItemDemandsResult,
    ]
):
    _demand_rules = MadeItemDemandRules
    _import_type = DataImportType.MADE_ITEM_DEMAND
    _result = ValidateBatchMadeItemDemandsResult

    def __init__(
        self,
        item_repo: IMadeItemQueries,
        project_repo: IProjectQueries,
        *,
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        super().__init__(_RowResolver(item_repo, project_repo), settings_repo=settings_repo)


class CommitBatchMadeItemDemandRows(
    CommitBatchDemands[
        MadeItemDemandItem,
        MadeItemBatchDemandRowInput,
        MadeItemResult,
        CommitBatchMadeItemDemandsResult,
    ]
):
    _spec = SPEC
    _demand_rules = MadeItemDemandRules
    _import_type = DataImportType.MADE_ITEM_DEMAND
    _result = CommitBatchMadeItemDemandsResult
    _log_kind = "batch made-item demand import"

    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        item_repo: IMadeItemQueries,
        project_repo: IProjectQueries,
        uow: IUnitOfWork,
        *,
        event_bus: IEventBus,
        reconciler: LifecycleReconciler,
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        super().__init__(
            demand_repo,
            project_repo,
            _RowResolver(item_repo, project_repo),
            uow,
            event_bus=event_bus,
            reconciler=reconciler,
            settings_repo=settings_repo,
        )

    def _new_demand(
        self,
        actor: User,
        row: MadeItemBatchDemandRowInput,
        item: MadeItemResult,
        project_id: int,
        project: Project,
    ) -> MadeItemDemandItem:
        now = now_utc()
        return MadeItemDemandItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Demand item created via batch import."),
            status=MadeItemDemandStatus.default(),
            quantity=row.quantity or 0,
            unit=_MADE_ITEM_DEMAND_UNIT,
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=row.note,
            desired_delivery_date=row.desired_delivery_date
            or (project.required_delivery_date_made if project else None),
            creator_id=actor.id,
            made_item_id=item.id,
            project_id=project_id,
            creator=actor,
            item_part_number=item.part_number or "",
            item_article_name=item.article_name,
            project_number=row.project_number or "",
            project_customer=(project.customer.name if project and project.customer else ""),
            project_description=(project.description or "") if project else "",
            project_status=project.status if project else ProjectStatus.ARCHIVED,
            is_alteration=False,
            alteration_of_made_item_id=None,
        )

    def _created_event(self, demand: MadeItemDemandItem) -> DomainEvent:
        return MadeItemDemandItemCreated(
            demand_id=demand.id,
            made_item_id=demand.made_item_id,
            project_id=demand.project_id,
            creator_id=demand.creator_id,
        )
