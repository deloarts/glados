"""
Validate and commit a batch of bought item demand rows parsed from a
user-uploaded Excel sheet on the frontend, through the batch use cases the
demand families share (_demand_family/batch_demands.py). This module holds
the bought item row resolver and the demand a row creates.

Lookup-only importer: a row's catalogue item is *found*, never created or
updated. Divergence between the file and the matched catalogue item (article
name, manufacturer, order code, part number) is reported as a warning only
and never applied. A row whose project is not active, or whose item new work
may not name, is invalid, since the demand it would create is refused.
"""

from typing import Literal

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import BoughtItemInactiveError
from src.modules.catalogue.domain.events.bought_item_events import DemandItemCreated
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.fulfillment.application.dto.bought_item_demand_dto import BatchDemandRowInput
from src.modules.fulfillment.application.dto.bought_item_demand_dto import CommitBatchDemandsResult
from src.modules.fulfillment.application.dto.bought_item_demand_dto import FieldDivergence
from src.modules.fulfillment.application.dto.bought_item_demand_dto import RowValidationResult
from src.modules.fulfillment.application.dto.bought_item_demand_dto import (
    ValidateBatchDemandsResult,
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
from src.modules.fulfillment.application.use_cases.bought_item_demand._demand_spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.services.bought_item_demand_rules import BoughtItemDemandRules
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
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

_MatchSource = Literal["part_number", "order_code_manufacturer"]


class _RowResolver:
    """Shared row-resolution logic used by both validate (read-only) and
    commit (re-validates from scratch before writing, never trusts
    client-cached validation state, since DB data may have changed since
    the user last clicked Validate).

    Lookup order: part number first (exact, normalized, non-deleted); if a
    part number is given but matches nothing, fall back to order code +
    manufacturer (also exact/normalized/non-deleted, order_code_1 only;
    order_code_2 is never consulted). Duplicate matches on either path
    block the row as 'ambiguous' rather than narrowing further."""

    def __init__(
        self,
        item_repo: IBoughtItemQueries,
        project_repo: IProjectQueries,
        supplier_repo: ISupplierQueries,
    ) -> None:
        self._items = item_repo
        self._projects = project_repo
        self._suppliers = supplier_repo

    async def resolve(self, row: BatchDemandRowInput) -> RowValidationResult:
        shape_errors = self._validate_row_shape(row)
        if shape_errors:
            return RowValidationResult(
                row_index=row.row_index, row_status="invalid", errors=shape_errors
            )

        has_part_number = self._has_part_number(row)
        has_fallback_key = self._has_fallback_key(row)

        # row_status precedence: a malformed row is invalid (above), then
        # unresolved_reference > ambiguous > not_found; a row that resolves
        # but whose demand would be refused is invalid; otherwise matched.
        # Project resolution is attempted regardless of the item-lookup
        # outcome, so the UI can surface a missing-project error alongside a
        # missing-item one.
        project, project_error = await resolve_project(self._projects, row.project_number)
        item_status, matched, match_source, item_errors = await self._resolve_item(
            row, has_part_number, has_fallback_key
        )
        refusals = new_demand_refusals(
            project,
            matched,
            assert_item_demandable=BoughtItemCatalogueRules.assert_item_demandable,
            item_error=BoughtItemInactiveError,
        )
        row_status, row_errors = decide_row_status(
            project_error, item_status, item_errors, refusals
        )

        divergences = (
            self._divergences(row, matched, match_source) if row_status == "matched" else []
        )

        return RowValidationResult(
            row_index=row.row_index,
            row_status=row_status,
            match_source=match_source,
            matched_item=BoughtItemMapper.to_result(matched) if matched else None,
            divergences=divergences,
            resolved_project_id=project.id if project else None,
            errors=row_errors,
        )

    @staticmethod
    def _has_part_number(row: BatchDemandRowInput) -> bool:
        return bool(row.part_number and row.part_number.strip())

    @staticmethod
    def _has_fallback_key(row: BatchDemandRowInput) -> bool:
        return bool(
            row.order_code
            and row.order_code.strip()
            and row.manufacturer_name
            and row.manufacturer_name.strip()
        )

    def _validate_row_shape(self, row: BatchDemandRowInput) -> list[str]:
        errors: list[str] = []
        if not row.project_number or not row.project_number.strip():
            errors.append("Project number is required.")
        if quantity := quantity_error(row.quantity, row.unit or ""):
            errors.append(quantity)
        if not row.unit or not row.unit.strip():
            errors.append("Unit is required.")
        if not self._has_part_number(row) and not self._has_fallback_key(row):
            errors.append(
                "Provide a part number, or an order code and manufacturer, to look up the item."
            )
        return errors

    async def _resolve_item(
        self, row: BatchDemandRowInput, has_part_number: bool, has_fallback_key: bool
    ) -> tuple[ItemLookupStatus, BoughtItem | None, _MatchSource | None, list[str]]:
        if has_part_number:
            assert row.part_number is not None
            item_status, matched, item_errors = await self._lookup_by_part_number(row.part_number)
            if item_status == "matched":
                return item_status, matched, "part_number", item_errors
            if item_status == "not_found" and has_fallback_key:
                assert row.order_code is not None
                assert row.manufacturer_name is not None
                (
                    item_status,
                    matched,
                    item_errors,
                ) = await self._lookup_by_order_code_and_manufacturer(
                    row.order_code, row.manufacturer_name
                )
                match_source: _MatchSource | None = (
                    "order_code_manufacturer" if item_status == "matched" else None
                )
                return item_status, matched, match_source, item_errors
            if item_status == "not_found":
                item_errors = [f"No catalogue item found for part number {row.part_number!r}."]
            return item_status, matched, None, item_errors

        assert row.order_code is not None
        assert row.manufacturer_name is not None
        item_status, matched, item_errors = await self._lookup_by_order_code_and_manufacturer(
            row.order_code, row.manufacturer_name
        )
        match_source = "order_code_manufacturer" if item_status == "matched" else None
        return item_status, matched, match_source, item_errors

    async def _lookup_by_part_number(
        self, part_number: str
    ) -> tuple[ItemLookupStatus, BoughtItem | None, list[str]]:
        # Strip before it hits the repo's substring (ILIKE '%term%') prefilter:
        # incidental surrounding whitespace in the uploaded cell must not make
        # the prefilter miss a value that is an exact match once normalized.
        # The repo prefilter is a substring ILIKE and get_multi pages at
        # DEFAULT_PAGE_SIZE, so a short value could push the exact match off
        # the first page, so ask for the largest page the repo allows.
        _, candidates = await self._items.get_multi(
            BoughtItemFilterDto(part_number=part_number.strip(), limit=MAX_PAGE_SIZE)
        )
        exact = [i for i in candidates if norm(i.part_number) == norm(part_number)]
        if len(exact) > 1:
            return (
                "ambiguous",
                None,
                [f"Multiple catalogue items share part number {part_number!r}."],
            )
        if len(exact) == 1:
            return "matched", exact[0], []
        return "not_found", None, []

    async def _lookup_by_order_code_and_manufacturer(
        self, order_code: str, manufacturer_name: str
    ) -> tuple[ItemLookupStatus, BoughtItem | None, list[str]]:
        # Same rationale as _lookup_by_part_number: strip before the repos'
        # substring prefilters so incidental whitespace can't hide an exact
        # (normalized) match.
        _, suppliers = await self._suppliers.get_multi(
            SupplierFilterDto(name=manufacturer_name.strip())
        )
        exact_supplier = next(
            (s for s in suppliers if norm(s.name) == norm(manufacturer_name)), None
        )
        if exact_supplier is None:
            return "not_found", None, [f"Manufacturer {manufacturer_name!r} not found."]

        _, candidates = await self._items.get_multi(
            BoughtItemFilterDto(
                order_code_1=order_code.strip(),
                manufacturer_id=exact_supplier.id,
                limit=MAX_PAGE_SIZE,
            )
        )
        exact = [
            i
            for i in candidates
            if norm(i.order_code_1) == norm(order_code) and i.manufacturer_id == exact_supplier.id
        ]
        if len(exact) > 1:
            return (
                "ambiguous",
                None,
                [
                    f"Multiple catalogue items share order code {order_code!r} for "
                    f"manufacturer {manufacturer_name!r}."
                ],
            )
        if len(exact) == 1:
            return "matched", exact[0], []
        return (
            "not_found",
            None,
            [
                f"No catalogue item found for order code {order_code!r} / "
                f"manufacturer {manufacturer_name!r}."
            ],
        )

    def _divergences(
        self,
        row: BatchDemandRowInput,
        matched: BoughtItem | None,
        match_source: _MatchSource | None,
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

        if match_source == "part_number":
            if row.manufacturer_name and norm(row.manufacturer_name) != norm(
                matched.manufacturer_name
            ):
                divergences.append(
                    FieldDivergence(
                        field="manufacturer_name",
                        db_value=matched.manufacturer_name,
                        file_value=row.manufacturer_name,
                    )
                )
            if row.order_code and norm(row.order_code) != norm(matched.order_code_1):
                divergences.append(
                    FieldDivergence(
                        field="order_code", db_value=matched.order_code_1, file_value=row.order_code
                    )
                )

        if match_source == "order_code_manufacturer":  # noqa: SIM102 - keep the match_source
            # branches visually separate; this mirrors the "part_number" branch above and a
            # merged condition would read as one undifferentiated check.
            if row.part_number and norm(row.part_number) != norm(matched.part_number):
                divergences.append(
                    FieldDivergence(
                        field="part_number",
                        db_value=matched.part_number,
                        file_value=row.part_number,
                    )
                )

        return divergences


class ValidateBatchDemandRows(
    ValidateBatchDemands[
        BoughtItemDemandItem, BatchDemandRowInput, RowValidationResult, ValidateBatchDemandsResult
    ]
):
    _demand_rules = BoughtItemDemandRules
    _import_type = DataImportType.BOUGHT_ITEM_DEMAND
    _result = ValidateBatchDemandsResult

    def __init__(
        self,
        item_repo: IBoughtItemQueries,
        project_repo: IProjectQueries,
        supplier_repo: ISupplierQueries,
        *,
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        super().__init__(
            _RowResolver(item_repo, project_repo, supplier_repo), settings_repo=settings_repo
        )


class CommitBatchDemandRows(
    CommitBatchDemands[
        BoughtItemDemandItem, BatchDemandRowInput, BoughtItemResult, CommitBatchDemandsResult
    ]
):
    _spec = SPEC
    _demand_rules = BoughtItemDemandRules
    _import_type = DataImportType.BOUGHT_ITEM_DEMAND
    _result = CommitBatchDemandsResult
    _log_kind = "batch demand import"

    def __init__(
        self,
        demand_repo: IBoughtItemDemandItemRepository,
        item_repo: IBoughtItemQueries,
        project_repo: IProjectQueries,
        supplier_repo: ISupplierQueries,
        uow: IUnitOfWork,
        *,
        event_bus: IEventBus,
        reconciler: LifecycleReconciler,
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        super().__init__(
            demand_repo,
            project_repo,
            _RowResolver(item_repo, project_repo, supplier_repo),
            uow,
            event_bus=event_bus,
            reconciler=reconciler,
            settings_repo=settings_repo,
        )

    def _new_demand(
        self,
        actor: User,
        row: BatchDemandRowInput,
        item: BoughtItemResult,
        project_id: int,
        project: Project,
    ) -> BoughtItemDemandItem:
        now = now_utc()
        return BoughtItemDemandItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Demand item created via batch import."),
            status=BoughtItemDemandStatus.default(),
            quantity=row.quantity or 0,
            unit=row.unit or "",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=row.note,
            desired_delivery_date=row.desired_delivery_date
            or (project.required_delivery_date_bought if project else None),
            creator_id=actor.id,
            item_id=item.id,
            project_id=project_id,
            creator=actor,
            item_order_code_1=item.order_code_1,
            item_article_name=item.article_name,
            project_number=row.project_number or "",
            project_customer="",
            project_description="",
            project_status=project.status if project else ProjectStatus.ARCHIVED,
        )

    def _created_event(self, demand: BoughtItemDemandItem) -> DomainEvent:
        return DemandItemCreated(
            demand_id=demand.id,
            item_id=demand.item_id,
            project_id=demand.project_id,
            creator_id=demand.creator_id,
        )
