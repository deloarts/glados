"""Converts a quote request aggregate to its result DTO, with each supplier's
offer totals and the cheapest offers worked out by the domain rules."""

from src.modules.fulfillment.application.dto.quote_request_dto import QuoteExtraCostResult
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestLineDemandResult
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestLineResult
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestResult
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestSupplierResult
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteResult
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.services.quote_request_rules import cheapest_complete_offer
from src.modules.fulfillment.domain.services.quote_request_rules import cheapest_per_line
from src.modules.fulfillment.domain.services.quote_request_rules import offer_totals
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.platform.application.mappers.user_mapper import UserMapper


class QuoteRequestMapper:
    @staticmethod
    def to_result(request: QuoteRequest, actions: list[str] | None = None) -> QuoteRequestResult:
        cheapest = cheapest_per_line(request)
        return QuoteRequestResult(
            id=request.id,
            public_id=request.public_id,
            request_number=request.request_number,
            status=QuoteRequestStatus(request.status),
            actions=actions or [],
            created=request.created,
            changed=request.changed,
            note=request.note,
            deadline=request.deadline,
            closed_at=request.closed_at,
            canceled_at=request.canceled_at,
            edit_version=request.edit_version,
            creator_id=request.creator_id,
            creator=UserMapper.to_public_result(request.creator) if request.creator else None,
            changed_by_id=request.changed_by_id,
            changed_by=(
                UserMapper.to_public_result(request.changed_by) if request.changed_by else None
            ),
            lines=[QuoteRequestMapper._line(line, cheapest.get(line.id)) for line in request.lines],
            suppliers=[QuoteRequestMapper._supplier(request, row) for row in request.suppliers],
            cheapest_complete_supplier_id=cheapest_complete_offer(request),
        )

    @staticmethod
    def _line(line: QuoteRequestLine, cheapest: int | None) -> QuoteRequestLineResult:
        return QuoteRequestLineResult(
            id=line.id,
            public_id=line.public_id,
            position=line.position,
            line_type=OrderLineType(line.line_type),
            quantity=line.quantity,
            unit=line.unit,
            created=line.created,
            note=line.note,
            item_name=line.item_name,
            item_code=line.item_code,
            bought_item_id=line.bought_item_id,
            source_item_id=line.source_item_id,
            lot_position_id=line.lot_position_id,
            lot_id=line.lot_id,
            lot_number=line.lot_number,
            virtual_name=line.virtual_name,
            project_id=line.project_id,
            project_number=line.project_number,
            state=line.state,
            awarded_supplier_id=line.awarded_supplier_id,
            awarded_price=line.awarded_price,
            awarded_at=line.awarded_at,
            award_voided=line.award_voided,
            dropped_at=line.dropped_at,
            order_item_id=line.order_item_id,
            order_id=line.order_id,
            order_number=line.order_number,
            substitute_reason=line.substitute_reason,
            substituted_by_line_id=line.substituted_by_line_id,
            demands=[
                QuoteRequestLineDemandResult(
                    family=QuoteRequestDemandFamily(d.family),
                    demand_item_id=d.demand_item_id,
                    quantity=d.quantity,
                )
                for d in line.demands
            ],
            cheapest_supplier_id=cheapest,
        )

    @staticmethod
    def _supplier(request: QuoteRequest, row: QuoteRequestSupplier) -> QuoteRequestSupplierResult:
        totals = offer_totals(request, row)
        live = [line for line in request.lines if line.state is not QuoteRequestLineState.DROPPED]
        return QuoteRequestSupplierResult(
            id=row.id,
            public_id=row.public_id,
            supplier_id=row.supplier_id,
            supplier_name=row.supplier_name,
            supplier_archived=row.supplier_archived,
            position=row.position,
            sent_at=row.sent_at,
            responded_at=row.responded_at,
            declined_at=row.declined_at,
            valid_until=row.valid_until,
            note=row.note,
            quotes=[
                QuoteResult(
                    line_id=q.line_id,
                    unit_price=q.unit_price,
                    no_offer=q.no_offer,
                    lead_time_days=q.lead_time_days,
                    min_quantity=q.min_quantity,
                    note=q.note,
                    substitute_bought_item_id=q.substitute_bought_item_id,
                    substitute_source_item_id=q.substitute_source_item_id,
                    substitute_reason=q.substitute_reason,
                    substitute_item_name=q.substitute_item_name,
                    substitute_item_code=q.substitute_item_code,
                )
                for q in row.quotes
            ],
            extra_costs=[
                QuoteExtraCostResult(
                    kind=ExtraCostKind(c.kind),
                    amount=c.amount,
                    position=c.position,
                    label=c.label,
                    note=c.note,
                    line_id=c.line_id,
                )
                for c in row.extra_costs
            ],
            lines_total=totals.lines_total,
            extra_costs_total=totals.extra_costs_total,
            total=totals.total,
            priced_lines=totals.priced_lines,
            not_asked_line_ids=[
                line.id
                for line in live
                if line.state is QuoteRequestLineState.OPEN and not row.asked_for(line)
            ],
            has_awarded_lines=any(
                line.awarded_supplier_id == row.id and line.state is QuoteRequestLineState.AWARDED
                for line in request.lines
            ),
        )
