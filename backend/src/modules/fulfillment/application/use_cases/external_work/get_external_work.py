"""
Lists the positions of external work across every live lot for
purchasing: what has to go to a supplier for an outside process such as
hardening or galvanizing, when it can go, by when it must go and when it
comes back. The repository filters, sorts and pages in SQL; the page is
then read through the lots, which carry the item, project and order line of
each position.
"""

from datetime import date

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.fulfillment.application.dto.external_work_dto import BackBySource
from src.modules.fulfillment.application.dto.external_work_dto import DateTermResult
from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkMethodResult
from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkPageResult
from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkQuery
from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkRowResult
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    describe_lot_target_dates,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.scheduling import resolve_position_lead_days
from src.modules.fulfillment.domain.services.scheduling.external_work import external_work_alert
from src.modules.fulfillment.domain.services.scheduling.external_work import inputs_ready
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import DateTerm
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    ExplanationInputs,
)
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    explain_external_work,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    ExternalWorkFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.shared_kernel.domain.services.clock import today_in


class GetExternalWork:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        supplier_queries: ISupplierQueries,
        settings_repo: IFulfillmentSettingsRepository,
        scheduling_repos: SchedulingRepos,
    ) -> None:
        self._lots = lot_repo
        self._suppliers = supplier_queries
        self._settings = settings_repo
        self._scheduling = scheduling_repos

    async def execute(self, query: ExternalWorkQuery) -> ExternalWorkPageResult:
        zone = await tenant_zone(self._settings)
        today = today_in(zone)
        total, page = await self._lots.get_external_work_page(
            ExternalWorkFilterDto(today=today, **query.model_dump())
        )
        if not page:
            return ExternalWorkPageResult(total=total, items=[])

        lots_by_id = {
            lot.id: lot
            for lot in await self._lots.get_by_ids(sorted({lot_id for _, lot_id in page}))
        }
        settings = await self._settings.get_production()
        default_lead_days = settings.default_external_lead_days
        supplier_names = await self._suggested_supplier_names(page, lots_by_id)
        targets = await describe_lot_target_dates(list(lots_by_id.values()), self._scheduling)

        items: list[ExternalWorkRowResult] = []
        for position_id, lot_id in page:
            lot = lots_by_id.get(lot_id)
            position = (
                next((p for p in lot.positions if p.id == position_id), None) if lot else None
            )
            if lot is None or position is None:
                # Gone between the page query and the read; the next load shows it.
                continue
            target_date, _source, demand_id = targets.get(lot.id, (None, None, None))
            inputs = ExplanationInputs(
                target_date=target_date,
                target_demand_id=demand_id,
                response_time_days=settings.response_time_days,
                safety_margin_days=settings.external_safety_margin_days,
                default_external_lead_days=default_lead_days,
                zone=zone,
                today=today,
            )
            items.append(
                _row(lot, position, default_lead_days, supplier_names, inputs, today=today)
            )
        return ExternalWorkPageResult(total=total, items=items)

    async def _suggested_supplier_names(
        self, page: list[tuple[int, int]], lots_by_id: dict[int, ProductionLot]
    ) -> dict[int, str]:
        """The names of the methods' default suppliers on the page, one read
        each, since a page names only a few."""
        position_ids = {position_id for position_id, _ in page}
        supplier_ids = {
            step.fabrication_method_default_supplier_id
            for lot in lots_by_id.values()
            for position in lot.positions
            if position.id in position_ids
            for step in position.steps
            if step.fabrication_method_default_supplier_id is not None
        }
        names: dict[int, str] = {}
        for supplier_id in sorted(supplier_ids):
            supplier = await self._suppliers.get_by_id(supplier_id)
            if supplier is not None:
                names[supplier_id] = supplier.name
        return names


def _suggested_supplier_id(position: LotPosition) -> int | None:
    """The default supplier of the first outsourced method of the position,
    else of its first method that has one."""
    fabrication = [s for s in position.steps if s.role == StepRole.FABRICATION]
    for step in sorted(
        fabrication, key=lambda s: (not s.fabrication_method_required_external, s.sequence)
    ):
        if step.fabrication_method_default_supplier_id is not None:
            return step.fabrication_method_default_supplier_id
    return None


def _row(
    lot: ProductionLot,
    position: LotPosition,
    default_lead_days: int,
    supplier_names: dict[int, str],
    inputs: ExplanationInputs,
    *,
    today: date,
) -> ExternalWorkRowResult:
    lead_days = resolve_position_lead_days(
        position.steps, position.order_item_supplier_external_lead_time_days, default_lead_days
    )
    back_by_source: BackBySource | None = None
    back_by_date = None
    if position.expected_delivery_date is not None:
        back_by_date, back_by_source = position.expected_delivery_date, "supplier"
    elif position.latest_delivery_date is not None:
        back_by_date = position.latest_delivery_date
        back_by_source = "latest_pickup"
    ready_now = inputs_ready(position, lot)
    explanation = explain_external_work(position, lot, inputs, ready_now=ready_now)
    suggested_id = _suggested_supplier_id(position) if position.order_item_id is None else None
    return ExternalWorkRowResult(
        position_id=position.id,
        position_sequence=position.sequence,
        kind=position.kind,
        position_status=position.status,
        lot_id=lot.id,
        lot_public_id=lot.public_id,
        lot_number=lot.lot_number,
        project_id=lot.project_id,
        project_number=lot.project_number,
        product_id=lot.product_id,
        product_number=lot.product_number,
        made_item_id=lot.made_item_id,
        made_item_public_id=lot.made_item_public_id,
        part_number=lot.made_item_part_number,
        article_name=lot.made_item_article_name,
        revision=lot.made_item_revision,
        quantity=position.quantity,
        handed_over_quantity=position.provisioned_quantity,
        fabrication_methods=[
            ExternalWorkMethodResult(
                id=step.fabrication_method_id, name=step.fabrication_method_name.as_dict()
            )
            for step in position.steps
            if step.role == StepRole.FABRICATION and step.fabrication_method_id is not None
        ],
        lead_days=lead_days,
        ready_now=ready_now,
        planned_pickup_date=position.planned_pickup_date,
        planned_delivery_date=position.planned_delivery_date,
        latest_pickup_date=position.latest_pickup_date,
        back_by_date=back_by_date,
        back_by_source=back_by_source,
        expected_pickup_date=position.order_item_expected_pickup_date,
        ready_for_pickup_date=position.order_item_ready_for_pickup_date,
        order_item_id=position.order_item_id,
        order_id=position.order_id,
        order_number=position.order_number,
        order_item_status=position.order_item_status,
        supplier_id=position.order_item_supplier_id,
        supplier_name=position.supplier_name,
        suggested_supplier_id=suggested_id,
        suggested_supplier_name=supplier_names.get(suggested_id, "") if suggested_id else "",
        alert=external_work_alert(position, ready_now=ready_now, today=today),
        ready_from_terms=_terms(explanation.ready_from),
        latest_pickup_terms=_terms(explanation.latest_pickup),
        back_by_terms=_terms(explanation.back_by),
        explanation_stale=explanation.stale,
    )


def _terms(terms: tuple[DateTerm, ...]) -> list[DateTermResult]:
    return [
        DateTermResult(
            kind=term.kind,
            date=term.date,
            days=term.days,
            minutes=term.minutes,
            methods=list(term.methods),
            source=term.source,
            reference=term.reference,
        )
        for term in terms
    ]
