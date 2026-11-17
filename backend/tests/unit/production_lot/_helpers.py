"""
Plain factory functions building minimal valid entities for the
production_lot test modules.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from tests.unit.production_order._helpers import give_status_facts


def make_made_item(
    id: int = 1,
    processes: list[MadeItemProcess] | None = None,
    bought_item_id: int | None = None,
    source_item_id: int | None = None,
) -> MadeItem:
    return MadeItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        revision="A",
        revision_date=None,
        revision_note=None,
        article_name="Bracket",
        status=MadeItemCatalogueStatus.ACTIVE,
        data_source=DataSource.WEB,
        part_number="MADE-0001",
        material="1.0037",
        mass=None,
        base_size=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        bought_item_id=bought_item_id,
        source_item_id=source_item_id,
        article_group_ids=[],
        successor_item_id=None,
        changed_by_id=None,
        processes=processes or [],
    )


def make_process(
    id: int,
    position: int,
    fabrication_method_id: int | None = 1,
    group_index: int | None = None,
    role: StepRole = StepRole.FABRICATION,
    inspection_method_id: int | None = None,
) -> MadeItemProcess:
    return MadeItemProcess(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        note=None,
        estimated_setup_minutes=10,
        estimated_minutes_per_piece=2.0,
        creator_id=1,
        fabrication_method_id=fabrication_method_id,
        made_item_id=1,
        position=position,
        group_index=group_index if group_index is not None else position,
        role=role,
        inspection_method_id=inspection_method_id,
    )


def make_fabrication_method(id: int = 1, archived: bool = False) -> FabricationMethod:
    return FabricationMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=LocalizedText({"enGB": f"Method {id}"}),
        label_color="#000000",
        label_font_color="#ffffff",
        description=LocalizedText(),
        creator_id=1,
        archived=archived,
    )


def make_order(id: int = 1, supplier_id: int = 1) -> Order:
    return Order(
        id=id,
        order_number=f"ORD-{id}",
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=OrderStatus.DRAFT,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        creator_id=1,
        supplier_id=supplier_id,
    )


def make_order_item(
    id: int = 1,
    order_id: int = 1,
    lot_position_id: int | None = None,
    line_type: OrderLineType = OrderLineType.MADE,
) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=OrderItemStatus.ORDERED,
        quantity=1.0,
        quantity_delivered=0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=order_id,
        supplier_id=1,
        project_id=1,
        line_type=line_type,
        lot_position_id=lot_position_id,
        source_item_id=None,
        virtual_name=None,
    )


def make_demand(
    id: int = 1,
    quantity: float = 10.0,
    high_priority: bool = False,
    made_item_id: int = 1,
    project_id: int = 1,
    status: MadeItemDemandStatus = MadeItemDemandStatus.OPEN,
    item_part_number: str | None = None,
    item_revision: str = "",
    item_article_name: str = "",
    project_number: str = "",
    project_customer: str = "",
    is_alteration: bool = False,
    alteration_of_made_item_id: int | None = None,
    desired_delivery_date: date | None = None,
) -> MadeItemDemandItem:
    return MadeItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=high_priority,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=desired_delivery_date,
        creator_id=1,
        made_item_id=made_item_id,
        project_id=project_id,
        is_alteration=is_alteration,
        alteration_of_made_item_id=alteration_of_made_item_id,
        item_part_number=item_part_number or "",
        item_revision=item_revision,
        item_article_name=item_article_name,
        project_number=project_number,
        project_customer=project_customer,
    )


def make_inspection_method(
    id: int = 1,
    archived: bool = False,
    default_setup_minutes: int | None = None,
    default_minutes_per_piece: float | None = None,
    default_machine_id: int | None = None,
):
    return InspectionMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=LocalizedText({"enGB": f"Inspection Method {id}"}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
        default_setup_minutes=default_setup_minutes,
        default_minutes_per_piece=default_minutes_per_piece,
        requires_evidence=False,
        archived=archived,
        default_machine_id=default_machine_id,
    )


def make_machine(
    id: int = 1,
    is_qa_machine: bool = False,
    archived: bool = False,
) -> ProductionMachine:
    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=archived,
        internal_name=f"Machine {id}",
        vendor="Contoso",
        model="VF-2",
        fabrication_method_ids=[],
        max_part_dimension=None,
        note=None,
        creator_id=1,
        is_qa_machine=is_qa_machine,
    )


def make_bought_item(
    id: int = 1, status: BoughtItemCatalogueStatus = BoughtItemCatalogueStatus.ACTIVE
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        article_name="Rod",
        order_code_1="ROD-1",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=status,
        data_source=DataSource.WEB,
        part_number=None,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=1,
        article_group_ids=[],
        successor_item_id=None,
    )


def make_source_item(
    id: int = 1, status: SourceItemCatalogueStatus = SourceItemCatalogueStatus.ACTIVE
) -> SourceItem:
    return SourceItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        type_id=1,
        dimension="40mm",
        material="1.0037",
        mass=None,
        note=None,
        order_code_1=None,
        order_code_2=None,
        status=status,
        creator_id=1,
        approver_id=None,
        manufacturer_id=None,
        successor_item_id=None,
    )


def make_source_item_demand(
    id: int = 1,
    lot_id: int = 1,
    project_id: int = 1,
    status: SourceItemDemandStatus = SourceItemDemandStatus.OPEN,
    bought_item_id: int | None = None,
    source_item_id: int | None = 1,
) -> SourceItemDemandItem:
    return SourceItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        quantity=5.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        bought_item_id=bought_item_id,
        source_item_id=source_item_id,
        lot_id=lot_id,
        project_id=project_id,
        status=status,
    )


def make_production_order(
    id: int,
    lot_position_id: int,
    status: ProductionOrderStatus = ProductionOrderStatus.IN_PROGRESS,
    machine_id: int | None = 1,
    quantity: float = 5.0,
    interruption_reason: InterruptionReason = InterruptionReason.MANUAL,
) -> ProductionOrder:
    """An order in `status`, with the facts the lifecycle reconciler derives
    that status from (production_order._helpers.give_status_facts)."""
    order = ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id:04d}",
        status=status,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=quantity,
        quantity_completed=0.0,
        estimated_duration_minutes=30,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=machine_id,
        lot_position_id=lot_position_id,
    )
    return give_status_facts(order, interruption_reason)


class NoLotCreation:
    """The lot creation of a piece disposition, for a test whose disposition
    spawns no rework or replacement lot; a call fails the test."""

    async def create_no_commit(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("This test's disposition was not expected to create a lot.")


class RecordingLotCreation:
    """The lot creation of a piece disposition, for a test that does not
    look at the follow-up lots: it records each command and answers with an
    unsaved lot built from it."""

    def __init__(self) -> None:
        self.commands: list[tuple[object, str | None]] = []

    async def create_no_commit(
        self,
        actor: object,
        cmd: object,
        *,
        origin_disposition: LotOriginDisposition | None = None,
        **_: object,
    ) -> ProductionLot:
        self.commands.append((cmd, origin_disposition))
        number = 9000 + len(self.commands)
        return ProductionLot(
            id=number,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            lot_number=f"LOS-FOLLOW-{number}",
            quantity=cmd.quantity,  # type: ignore[attr-defined]
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=cmd.made_item_id,  # type: ignore[attr-defined]
            project_id=cmd.project_id,  # type: ignore[attr-defined]
            input_demand_id=None,
            origin_disposition=origin_disposition,
        )
