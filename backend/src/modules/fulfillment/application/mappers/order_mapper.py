"""Converts between Order/OrderItem domain entities and DTOs, including delivery records and
substitutions."""

from src.modules.fulfillment.application.dto.order_dto import DeliveryRecordInfo
from src.modules.fulfillment.application.dto.order_dto import DemandSubstitutionInfo
from src.modules.fulfillment.application.dto.order_dto import OrderExtraCostResult
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderQuoteRequestResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_extra_cost import OrderExtraCost
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.services.extra_cost_rules import PricedLine
from src.modules.fulfillment.domain.services.extra_cost_rules import extra_costs_total
from src.modules.fulfillment.domain.services.extra_cost_rules import lines_total
from src.modules.fulfillment.domain.services.extra_cost_rules import net_total
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.platform.application.mappers.user_mapper import UserMapper


class OrderMapper:
    @staticmethod
    def to_result(
        entity: Order,
        items: list[OrderItem] | None = None,
        substitutions_by_item_id: dict[int, list[DemandSubstitutionInfo]] | None = None,
        delivery_records_by_item_id: dict[int, list[OrderItemDelivery]] | None = None,
    ) -> OrderResult:
        subs = substitutions_by_item_id or {}
        deliveries = delivery_records_by_item_id or {}
        lines = sorted(items or [], key=lambda i: i.position)
        return OrderResult(
            id=entity.id,
            public_id=entity.public_id,
            order_number=entity.order_number,
            status=entity.status,
            created=entity.created,
            changed=entity.changed,
            note=entity.note,
            ordered_date=entity.ordered_date,
            expected_delivery_date=entity.expected_delivery_date,
            delivery_date=entity.delivery_date,
            storage_place=entity.storage_place,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            supplier_id=entity.supplier_id,
            supplier_name=entity.supplier_name,
            supplier_vat_id=entity.supplier_vat_id,
            supplier_archived=entity.supplier_archived,
            requested_at=entity.requested_at,
            canceled_at=entity.canceled_at,
            edit_version=entity.edit_version,
            items=[
                OrderItemMapper.to_result(
                    i,
                    demand_substitutions=subs.get(i.id, []),
                    delivery_records=deliveries.get(i.id, []),
                )
                for i in lines
            ],
            extra_costs=[OrderMapper.extra_cost_result(c) for c in entity.extra_costs],
            quote_requests=[
                OrderQuoteRequestResult(id=r.id, request_number=r.request_number)
                for r in entity.quote_requests
            ],
            **OrderMapper._totals(entity, lines),
            total_items=sum(i.quantity * i.items_per_unit for i in lines),
            orderer_full_name=next((i.orderer.full_name for i in lines if i.orderer), ""),
            delivered_by_full_name=OrderMapper._last_receiver_name(lines),
        )

    @staticmethod
    def extra_cost_result(cost: OrderExtraCost) -> OrderExtraCostResult:
        return OrderExtraCostResult(
            id=cost.id,
            public_id=cost.public_id,
            kind=ExtraCostKind(cost.kind),
            amount=cost.amount,
            position=cost.position,
            label=cost.label,
            note=cost.note,
            order_item_id=cost.order_item_id,
        )

    @staticmethod
    def _totals(entity: Order, lines: list[OrderItem]) -> dict[str, int | None]:
        """The order's totals in net cents. Without its lines, as a write
        answers, only the extra costs are known, so the line and net totals
        are None there as well."""
        costs = extra_costs_total((c.kind, c.amount) for c in entity.extra_costs)
        line_sum = lines_total(
            PricedLine(price=i.price, quantity=i.quantity, canceled=i.canceled_at is not None)
            for i in lines
        )
        return {
            "lines_total": line_sum,
            "extra_costs_total": costs,
            "net_total": net_total(line_sum, costs, has_costs=bool(entity.extra_costs)),
        }

    @staticmethod
    def _last_receiver_name(lines: list[OrderItem]) -> str:
        """Who received the most recent delivery on this order. Lines are
        delivered independently and a partially delivered order has several
        receivers; the docket shows the latest one rather than inventing a
        list."""
        delivered = [
            (i.delivery_date, i.receiver.full_name)
            for i in lines
            if i.receiver is not None and i.delivery_date is not None
        ]
        return max(delivered)[1] if delivered else ""


class OrderItemMapper:
    @staticmethod
    def to_result(
        entity: OrderItem,
        demand_substitutions: list[DemandSubstitutionInfo] | None = None,
        delivery_records: list[OrderItemDelivery] | None = None,
    ) -> OrderItemResult:
        return OrderItemResult(
            id=entity.id,
            public_id=entity.public_id,
            status=entity.status,
            created=entity.created,
            changed=entity.changed,
            position=entity.position,
            quantity=entity.quantity,
            quantity_delivered=entity.quantity_delivered,
            quantity_rejected=entity.quantity_rejected,
            quantity_rejected_lost=entity.quantity_rejected_lost,
            unit=entity.unit,
            items_per_unit=entity.items_per_unit,
            price=entity.price,
            note=entity.note,
            ordered_date=entity.ordered_date,
            expected_delivery_date=entity.expected_delivery_date,
            delivery_date=entity.delivery_date,
            storage_place=entity.storage_place,
            expected_pickup_date=entity.expected_pickup_date,
            ready_for_pickup_date=entity.ready_for_pickup_date,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            orderer_id=entity.orderer_id,
            orderer=UserMapper.to_public_result(entity.orderer) if entity.orderer else None,
            receiver_id=entity.receiver_id,
            receiver=UserMapper.to_public_result(entity.receiver) if entity.receiver else None,
            bought_item_id=entity.bought_item_id,
            source_item_id=entity.source_item_id,
            virtual_name=entity.virtual_name,
            quote_request_line_id=entity.quote_request_line_id,
            quote_request_id=entity.quote_request_id,
            quote_request_number=entity.quote_request_number,
            item_order_code_1=entity.item_order_code_1,
            item_order_code_2=entity.item_order_code_2,
            item_specification=entity.item_specification,
            item_article_name=entity.item_article_name,
            item_part_number=entity.item_part_number,
            item_material=entity.item_material,
            item_dimension=entity.item_dimension,
            item_type_name=entity.item_type_name,
            item_revision=entity.item_revision,
            item_base_size=entity.item_base_size,
            item_mass=entity.item_mass,
            item_manufacturer=entity.item_manufacturer,
            made_item_id=entity.made_item_id,
            order_id=entity.order_id,
            supplier_id=entity.supplier_id,
            supplier_name=entity.supplier_name,
            project_id=entity.project_id,
            project_number=entity.project_number,
            product_number=entity.product_number,
            project_customer=entity.project_customer,
            project_description=entity.project_description,
            project_status=entity.project_status,
            line_type=entity.line_type,
            lot_position_id=entity.lot_position_id,
            lot_id=entity.lot_id,
            lot_number=entity.lot_number,
            fabrication_method=entity.fabrication_method,
            requested_at=entity.requested_at,
            canceled_at=entity.canceled_at,
            edit_version=entity.edit_version,
            closed_short_at=entity.closed_short_at,
            closed_short_from=entity.closed_short_from,
            demand_substitutions=demand_substitutions or [],
            delivery_records=[
                DeliveryRecordInfo(
                    id=d.id,
                    public_id=d.public_id,
                    quantity=d.quantity,
                    delivery_date=d.delivery_date,
                    storage_place=d.storage_place,
                    receiver_id=d.receiver_id,
                    receiver=UserMapper.to_public_result(d.receiver) if d.receiver else None,
                    quantity_rejected=d.quantity_rejected,
                    rejection_reason=d.rejection_reason,
                    rejection_note=d.rejection_note,
                    rejection_outcome=d.rejection_outcome,
                    corrects_delivery_id=d.corrects_delivery_id,
                    correction_reason=d.correction_reason,
                    supplier_batch=d.supplier_batch,
                    delivery_note_number=d.delivery_note_number,
                    certificate_reference=d.certificate_reference,
                    damage_noted_on_delivery_note=d.damage_noted_on_delivery_note,
                )
                for d in delivery_records or []
            ],
        )
