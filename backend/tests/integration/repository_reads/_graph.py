"""
The seeded row graph the read scenarios run against. Nodes are created on
first request, through the real repositories, with every optional foreign
key set that the schema allows, so mappers follow many-to-one relationships
instead of short-circuiting on a NULL key. `make` keeps entity construction
short by filling fields a scenario does not care about.
"""

import dataclasses
import functools
import itertools
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.repositories.article_group_repository import (
    SqlAlchemyArticleGroupRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.contact_repository import (
    SqlAlchemyContactRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.customer_repository import (
    SqlAlchemyCustomerRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.inspection_method_repository import (
    SqlAlchemyInspectionMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.product_family_repository import (
    SqlAlchemyProductFamilyRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_type_repository import (
    SqlAlchemySourceItemTypeRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.entities.product_family import ProductFamily
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_demand_bucket_repository import (
    SqlAlchemyBoughtItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_bucket_repository import (
    SqlAlchemyMadeItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.allocation import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.delivery import (
    SqlAlchemyOrderItemDeliveryRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_bucket_repository import (
    SqlAlchemySourceItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_bucket import BoughtItemDemandBucket
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_position_provision import LotPositionProvision
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_bucket import MadeItemDemandBucket
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_bucket import SourceItemDemandBucket
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.quality.adapters.outbound.persistence.models.print_template_model import (
    PrintTemplateOrmModel,
)
from src.modules.quality.adapters.outbound.persistence.repositories.calculation_repository import (
    SqlAlchemyCalculationRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.checklist_repository import (
    SqlAlchemyChecklistRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.printer_repository import (
    SqlAlchemyPrinterRepository,
)
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.value_objects.checklist_answer import ChecklistVerdict
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_repository import (
    SqlAlchemyMeetingRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_repository import (
    SqlAlchemyProductDeviceRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_resource_repository import (
    SqlAlchemyProductDeviceKindRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_resource_repository import (
    SqlAlchemyProductDeviceOptionRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_file_repository import (
    SqlAlchemyProductFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingAttendee
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindParameter
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_device_option import ProductDeviceOption
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_parameter_type import (
    ProductDeviceParameterType,
)
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from tests.integration._demand_facts import give_demand_facts
from tests.integration._lot_facts import give_lot_facts
from tests.integration.conftest import make_user_entity

# ── Entity construction ──────────────────────────────────────────────

NOW = datetime.now(UTC).replace(microsecond=0)
TODAY = NOW.date()
_DEFAULTS: dict[str, Callable[[], object]] = {
    "datetime": lambda: NOW,
    "date": lambda: TODAY,
    "str": lambda: "x",
    "float": lambda: 1.0,
    "int": lambda: 0,
    "bool": lambda: False,
    "list": list,
    "dict": dict,
    "LocalizedText": LocalizedText,
}


def make[T](cls: type[T], **values: Any) -> T:
    """Builds an entity, filling every required field the caller did not
    pass with a neutral value for its annotated type (None for optional
    fields). Enum and Literal fields have no neutral value and must be
    passed explicitly; a KeyError here names the missing one."""
    for f in dataclasses.fields(cls):  # type: ignore[arg-type]
        if f.name in values or f.name == "id" or f.init is False:
            continue
        if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING:
            continue
        if "None" in str(f.type):
            values[f.name] = None
            continue
        type_name = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", "")
        values[f.name] = _DEFAULTS[type_name.split("[")[0]]()
    if "id" in {f.name for f in dataclasses.fields(cls)}:  # type: ignore[arg-type]
        values.setdefault("id", 0)
    return cls(**values)


# ── Seeding ──────────────────────────────────────────────────────────


@functools.cache
def _user_template() -> User:
    """Hashing a password costs a bcrypt round, so it is done once for the
    module and every seeded user is a copy."""
    return make_user_entity()


def _memo[R](fn: Callable[["Graph"], Awaitable[R]]) -> Callable[["Graph"], Awaitable[R]]:
    """Seeds a node of the graph once per test, however many scenarios or
    other nodes ask for it."""

    @functools.wraps(fn)
    async def wrapper(self: "Graph") -> R:
        if fn.__name__ not in self._cache:
            self._cache[fn.__name__] = await fn(self)
        return self._cache[fn.__name__]  # type: ignore[no-any-return]

    return wrapper


_seq = itertools.count(1)


def file_fields(prefix: str) -> dict[str, Any]:
    n = next(_seq)
    return {
        "file_name": f"{prefix}-{n}.pdf",
        "stored_name": f"{prefix}-{n}",
        "mime_type": "application/pdf",
        "size_bytes": 10,
        "storage_path": f"{prefix}/{n}",
        "sha256": "0" * 64,
        "created": NOW,
    }


class Graph:
    """A lazily seeded, fully linked row graph. Every node is created on
    first request through the real repository on the seeding session and
    committed, so the reading session only ever sees committed rows."""

    def __init__(self, db: AsyncSession, user: User, other_user: User) -> None:
        self.db = db
        self.user = user
        self.other_user = other_user
        self._cache: dict[str, object] = {}

    @classmethod
    async def seed(cls, db: AsyncSession) -> "Graph":
        """Two users to start from, so creator and approver style links can
        point at different rows."""
        users = SqlAlchemyUserRepository(db)
        template = _user_template()
        user = await users.save(dataclasses.replace(template, public_id=uuid4()))
        other = await users.save(
            dataclasses.replace(
                template, public_id=uuid4(), username="other", email="other@example.com"
            )
        )
        await db.commit()
        return cls(db, user, other)

    @property
    def uid(self) -> int:
        return self.user.id

    @_memo
    async def article_group(self) -> ArticleGroup:
        saved = await SqlAlchemyArticleGroupRepository(self.db).save(
            make(ArticleGroup, name=LocalizedText({"enGB": "Fasteners"}), creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def product_family(self) -> ProductFamily:
        saved = await SqlAlchemyProductFamilyRepository(self.db).save(
            make(ProductFamily, name="Cylinders", creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def fabrication_method(self) -> FabricationMethod:
        saved = await SqlAlchemyFabricationMethodRepository(self.db).save(
            make(FabricationMethod, name=LocalizedText({"enGB": "Milling"}), creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def inspection_method(self) -> InspectionMethod:
        saved = await SqlAlchemyInspectionMethodRepository(self.db).save(
            make(
                InspectionMethod, name=LocalizedText({"enGB": "Visual check"}), creator_id=self.uid
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def supplier(self) -> Supplier:
        method = await self.fabrication_method()
        group = await self.article_group()
        saved = await SqlAlchemySupplierRepository(self.db).save(
            make(
                Supplier,
                name="Acme",
                vat_id="ATU1",
                edp_code="SIE",
                level=SupplierLevel.A,
                capability_ids=[method.id],
                article_group_ids=[group.id],
                creator_id=self.uid,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def customer(self) -> Customer:
        saved = await SqlAlchemyCustomerRepository(self.db).save(
            make(
                Customer, name="Customer", vat_id="ATU2", level=CustomerLevel.A, creator_id=self.uid
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def product(self) -> Product:
        customer = await self.customer()
        saved = await SqlAlchemyProductRepository(self.db).save(
            Product(
                id=0,
                created=NOW,
                product_number="PR-1",
                customer_id=customer.id,
                designated_user_id=self.uid,
                creator_id=self.uid,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def project(self) -> Project:
        customer = await self.customer()
        product = await self.product()
        saved = await SqlAlchemyProjectRepository(self.db).save(
            Project(
                id=0,
                created=NOW,
                project_number="P-1",
                customer_id=customer.id,
                product_id=product.id,
                designated_user_id=self.uid,
                creator_id=self.uid,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def customer_contact(self) -> Contact:
        """A contact of the customer with an e-mail address, so it is
        offered as a recipient of the customer's mails."""
        saved = await SqlAlchemyContactRepository(self.db).save(
            make(
                Contact,
                created=NOW,
                name="Anna Contact 1",
                email="anna@example.com",
                customer_id=(await self.customer()).id,
                creator_id=self.uid,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def supplier_contact(self) -> Contact:
        """A contact of the supplier that receives its request and order
        mails."""
        saved = await SqlAlchemyContactRepository(self.db).save(
            make(
                Contact,
                created=NOW,
                name="Ben Contact 1",
                email="ben@example.com",
                supplier_id=(await self.supplier()).id,
                receives_request_mails=True,
                receives_order_mails=True,
                creator_id=self.uid,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def meeting(self) -> Meeting:
        """A meeting of the project that started yesterday, numbered like
        every other seeded number, with a user and the customer's contact
        among its attendees and one tag."""
        contact = await self.customer_contact()
        starts_at = NOW - timedelta(days=1)
        saved = await SqlAlchemyMeetingRepository(self.db).save(
            Meeting(
                id=0,
                meeting_number="MTG-26-0001",
                name="Kick-off 1",
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=1),
                created=NOW,
                creator_id=self.uid,
                project_id=(await self.project()).id,
                attendees=[
                    MeetingAttendee(
                        id=0,
                        kind=MeetingAttendeeKind.USER,
                        status=MeetingAttendanceStatus.PRESENT,
                        user_id=self.uid,
                    ),
                    MeetingAttendee(
                        id=0,
                        kind=MeetingAttendeeKind.CONTACT,
                        status=MeetingAttendanceStatus.DISTRIBUTION_ONLY,
                        contact_id=contact.id,
                        name=contact.name,
                        email=contact.email,
                    ),
                ],
                tags=["Milestone"],
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def source_item_type(self) -> SourceItemType:
        saved = await SqlAlchemySourceItemTypeRepository(self.db).save(
            make(SourceItemType, name=LocalizedText({"enGB": "Round bar"}), creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def source_item(self) -> SourceItem:
        item_type = await self.source_item_type()
        supplier = await self.supplier()
        saved = await SqlAlchemySourceItemRepository(self.db).save(
            make(
                SourceItem,
                type_id=item_type.id,
                dimension="D 1",
                material="S235",
                status=SourceItemCatalogueStatus.ACTIVE,
                creator_id=self.uid,
                approver_id=self.other_user.id,
                manufacturer_id=supplier.id,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def bought_item(self) -> BoughtItem:
        supplier = await self.supplier()
        group = await self.article_group()
        family = await self.product_family()
        saved = await SqlAlchemyBoughtItemRepository(self.db).save(
            make(
                BoughtItem,
                article_name="Screw M6",
                order_code_1="OC-1",
                gtin="4006381333931",
                status=BoughtItemCatalogueStatus.ACTIVE,
                data_source=DataSource.CAD,
                part_number="B-1",
                files=[],
                creator_id=self.uid,
                approver_id=self.other_user.id,
                manufacturer_id=supplier.id,
                article_group_ids=[group.id],
                product_family_id=family.id,
                ean="4006381333955",
                edp_part_id=451627,
                vault_id="vault",
                pdm_file_id=11,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def made_item(self) -> MadeItem:
        group = await self.article_group()
        source_item = await self.source_item()
        seeded = await SqlAlchemyMadeItemRepository(self.db).save(
            make(
                MadeItem,
                revision="0",
                article_name="Bracket",
                status=MadeItemCatalogueStatus.ACTIVE,
                data_source=DataSource.CAD,
                part_number="M-1",
                material="S235",
                files=[],
                creator_id=self.uid,
                approver_id=self.other_user.id,
                source_item_id=source_item.id,
                article_group_ids=[group.id],
                vault_id="vault",
                pdm_file_id=12,
            )
        )
        await self.db.commit()
        return seeded

    @_memo
    async def made_item_process(self) -> MadeItemProcess:
        item = await self.made_item()
        method = await self.fabrication_method()
        return await SqlAlchemyMadeItemRepository(self.db).save_process(
            make(
                MadeItemProcess,
                fabrication_method_id=method.id,
                made_item_id=item.id,
                position=1,
                group_index=0,
                creator_id=self.uid,
            )
        )

    @_memo
    async def machine(self) -> ProductionMachine:
        method = await self.fabrication_method()
        saved = await SqlAlchemyProductionMachineRepository(self.db).save(
            make(
                ProductionMachine,
                internal_name="MILL-1",
                fabrication_method_ids=[method.id],
                creator_id=self.uid,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def machine_pool(self) -> MachinePool:
        machine = await self.machine()
        saved = await SqlAlchemyMachinePoolRepository(self.db).save(
            make(MachinePool, name="Mills", machine_ids=[machine.id], creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def lot(self) -> ProductionLot:
        made_item = await self.made_item()
        project = await self.project()
        source_item = await self.source_item()
        saved = await SqlAlchemyProductionLotRepository(self.db).save(
            make(
                ProductionLot,
                lot_number="L-1",
                quantity=10.0,
                status=LotStatus.PLANNED,
                priority=UrgencyClass.NORMAL,
                creator_id=self.uid,
                made_item_id=made_item.id,
                project_id=project.id,
                input_demand_id=None,
                source_item_id=source_item.id,
            )
        )
        await self.db.commit()
        return await self._settled_lot(saved.id)

    async def _settled_lot(self, lot_id: int) -> ProductionLot:
        """Lets the lifecycle reconciler store what the lot's facts derive
        for it and its positions, as a use case does after each change, and
        returns the lot as stored then."""
        # The builders add facts after the lot was seeded, so its stored
        # status is expected to move.
        await give_lot_facts(self.db, lot_id, exact=False)
        await self.db.commit()
        lot = await SqlAlchemyProductionLotRepository(self.db).get_by_id(lot_id)
        assert lot is not None
        return lot

    async def _settle_lot(self) -> None:
        self._cache["lot"] = await self._settled_lot((await self.lot()).id)

    @_memo
    async def made_item_revision(self) -> MadeItem:
        """A second revision of the same part, sourced from a bought item
        instead of a source item, so both mapper branches run."""
        item = await self.made_item()
        bought = await self.bought_item()
        seeded = await SqlAlchemyMadeItemRepository(self.db).save(
            dataclasses.replace(
                item,
                id=0,
                public_id=uuid4(),
                revision="1",
                source_item_id=None,
                bought_item_id=bought.id,
                changed_by_id=self.other_user.id,
            )
        )
        await self.db.commit()
        return seeded

    @_memo
    async def follow_up_lots(self) -> list[ProductionLot]:
        """Lots spawned from the main lot, one reworking the made item and
        one drawing a bought item, covering the other material sources and
        the origin and follow-up links."""
        lot = await self.lot()
        bought = await self.bought_item()
        repo = SqlAlchemyProductionLotRepository(self.db)
        base = dataclasses.replace(
            lot, id=0, status=LotStatus.DRAFT, source_item_id=None, input_demand_id=None
        )
        rework = await repo.save(
            dataclasses.replace(
                base,
                public_id=uuid4(),
                lot_number="L-2",
                origin_lot_id=lot.id,
                origin_disposition=LotOriginDisposition.REWORK,
                source_made_item_id=lot.made_item_id,
            )
        )
        bought_lot = await repo.save(
            dataclasses.replace(
                base, public_id=uuid4(), lot_number="L-3", source_bought_item_id=bought.id
            )
        )
        return [rework, bought_lot]

    @_memo
    async def internal_position(self) -> LotPosition:
        lot = await self.lot()
        method = await self.fabrication_method()
        repo = SqlAlchemyProductionLotRepository(self.db)
        position = await repo.save_position(
            make(
                LotPosition,
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=10.0,
                quantity_completed=0.0,
                creator_id=self.uid,
                lot_id=lot.id,
            )
        )
        await repo.save_step(
            make(
                LotStep,
                sequence=1,
                creator_id=self.uid,
                fabrication_method_id=method.id,
                lot_id=lot.id,
                position_id=position.id,
                source_process_id=(await self.made_item_process()).id,
            )
        )
        await self._settle_lot()
        return position

    @_memo
    async def external_position(self) -> LotPosition:
        lot = await self.lot()
        inspection = await self.inspection_method()
        repo = SqlAlchemyProductionLotRepository(self.db)
        position = await repo.save_position(
            make(
                LotPosition,
                sequence=2,
                kind=LotPositionKind.EXTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=10.0,
                quantity_completed=0.0,
                creator_id=self.uid,
                lot_id=lot.id,
            )
        )
        await repo.save_step(
            make(
                LotStep,
                sequence=2,
                role=StepRole.INSPECTION,
                inspection_method_id=inspection.id,
                creator_id=self.uid,
                fabrication_method_id=None,
                lot_id=lot.id,
                position_id=position.id,
                source_process_id=None,
            )
        )
        await self._settle_lot()
        return position

    @_memo
    async def provision(self) -> LotPositionProvision:
        position = await self.internal_position()
        saved = await SqlAlchemyProductionLotRepository(self.db).save_provision(
            make(LotPositionProvision, lot_position_id=position.id, creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def lot_event(self) -> LotEvent:
        lot = await self.lot()
        saved = await SqlAlchemyProductionLotRepository(self.db).record_event(
            make(
                LotEvent,
                lot_id=lot.id,
                actor_id=self.uid,
                event_type=LotEventType.LOT_CREATED,
                entity="lot",
                entity_id=lot.id,
                summary="created",
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def production_order(self) -> ProductionOrder:
        position = await self.internal_position()
        machine = await self.machine()
        pool = await self.machine_pool()
        saved = await SqlAlchemyProductionOrderRepository(self.db).save(
            make(
                ProductionOrder,
                production_order_number="PO-1",
                status=ProductionOrderStatus.IN_PROGRESS,
                priority=UrgencyClass.NORMAL,
                pinned=False,
                queue_sequence=1,
                quantity=10.0,
                quantity_completed=0.0,
                estimated_duration_minutes=30,
                planned_start=NOW,
                planned_end=NOW + timedelta(hours=1),
                actual_start=NOW,
                creator_id=self.uid,
                machine_id=machine.id,
                machine_pool_id=pool.id,
                planned_by_id=self.uid,
                started_operator_id=self.other_user.id,
                lot_position_id=position.id,
            )
        )
        await self.db.commit()
        await self._settle_lot()
        return saved

    @_memo
    async def completion(self) -> ProductionOrderCompletion:
        order = await self.production_order()
        saved = await SqlAlchemyProductionOrderRepository(self.db).save_completion(
            make(
                ProductionOrderCompletion,
                production_order_id=order.id,
                quantity=2.0,
                quantity_accepted=2.0,
                quantity_rejected=0.0,
                operator_id=self.other_user.id,
                recorded_by_id=self.uid,
            )
        )
        # The completed count the reconciler derives from the row, written
        # without a version bump so the order the graph holds stays current.
        await self.db.execute(
            update(ProductionOrderOrmModel)
            .where(ProductionOrderOrmModel.id == order.id)
            .values(quantity_completed=ProductionOrderOrmModel.quantity_completed + 2.0)
        )
        await self.db.commit()
        await self._settle_lot()
        return saved

    @_memo
    async def interruption(self) -> ProductionOrderInterruption:
        order = await self.production_order()
        saved = await SqlAlchemyProductionOrderInterruptionRepository(self.db).add(
            make(
                ProductionOrderInterruption,
                production_order_id=order.id,
                paused_at=NOW - timedelta(minutes=30),
                resumed_at=NOW,
                paused_by_id=self.uid,
                resumed_by_id=self.other_user.id,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def order(self) -> Order:
        supplier = await self.supplier()
        saved = await SqlAlchemyOrderRepository(self.db).save(
            make(
                Order,
                order_number="O-1",
                status=OrderStatus.ORDERED,
                ordered_date=NOW,
                expected_delivery_date=TODAY,
                creator_id=self.uid,
                supplier_id=supplier.id,
            )
        )
        await self.db.commit()
        return saved

    async def _order_item(self, **values: Any) -> OrderItem:
        order = await self.order()
        project = await self.project()
        saved = await SqlAlchemyOrderItemRepository(self.db).save(
            make(
                OrderItem,
                status=OrderItemStatus.ORDERED,
                quantity=10.0,
                quantity_delivered=0.0,
                unit="pcs",
                ordered_date=NOW,
                expected_delivery_date=TODAY,
                creator_id=self.uid,
                orderer_id=self.uid,
                receiver_id=self.other_user.id,
                order_id=order.id,
                supplier_id=order.supplier_id,
                project_id=project.id,
                position=next(_seq),
                **values,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def bought_order_item(self) -> OrderItem:
        item = await self.bought_item()
        return await self._order_item(line_type=OrderLineType.BOUGHT, bought_item_id=item.id)

    @_memo
    async def source_order_item(self) -> OrderItem:
        item = await self.source_item()
        return await self._order_item(line_type=OrderLineType.SOURCE, source_item_id=item.id)

    @_memo
    async def made_order_item(self) -> OrderItem:
        position = await self.external_position()
        line = await self._order_item(line_type=OrderLineType.MADE, lot_position_id=position.id)
        await self._settle_lot()
        return line

    @_memo
    async def delivery(self) -> OrderItemDelivery:
        """Four pieces delivered on the bought line, booked on the line and
        its order as a delivery books them, so their stored totals and
        statuses agree with the row."""
        item = await self.bought_order_item()
        saved = await SqlAlchemyOrderItemDeliveryRepository(self.db).save(
            make(
                OrderItemDelivery,
                order_item_id=item.id,
                quantity=4.0,
                delivery_date=NOW,
                receiver_id=self.other_user.id,
            )
        )
        item.quantity_delivered = 4.0
        item.status = OrderItemStatus.PARTIALLY_DELIVERED
        item.delivery_date = NOW
        await SqlAlchemyOrderItemRepository(self.db).save(item)
        order = await self.order()
        order.status = OrderStatus.PARTIALLY_DELIVERED
        await SqlAlchemyOrderRepository(self.db).save(order)
        await self.db.commit()
        return saved

    async def _demand_fields(self) -> dict[str, Any]:
        project = await self.project()
        return {
            "quantity": 10.0,
            "unit": "pcs",
            "items_per_unit": 1.0,
            "high_priority": False,
            "notify_on_delivery": True,
            "desired_delivery_date": TODAY,
            "creator_id": self.uid,
            "project_id": project.id,
        }

    @_memo
    async def made_bucket(self) -> MadeItemDemandBucket:
        saved = await SqlAlchemyMadeItemDemandBucketRepository(self.db).save(
            make(MadeItemDemandBucket, name="Urgent", color="#ff0000", creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def bought_bucket(self) -> BoughtItemDemandBucket:
        saved = await SqlAlchemyBoughtItemDemandBucketRepository(self.db).save(
            make(BoughtItemDemandBucket, name="Urgent", color="#ff0000", creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def source_bucket(self) -> SourceItemDemandBucket:
        saved = await SqlAlchemySourceItemDemandBucketRepository(self.db).save(
            make(SourceItemDemandBucket, name="Urgent", color="#ff0000", creator_id=self.uid)
        )
        await self.db.commit()
        return saved

    @_memo
    async def made_demand(self) -> MadeItemDemandItem:
        item = await self.made_item()
        bucket = await self.made_bucket()
        saved = await SqlAlchemyMadeItemDemandItemRepository(self.db).save(
            make(
                MadeItemDemandItem,
                made_item_id=item.id,
                bucket_id=bucket.id,
                status=MadeItemDemandStatus.ALLOCATED,
                **await self._demand_fields(),
            )
        )
        await self.db.commit()
        return await self._settled_made_demand(saved.id)

    async def _settled_made_demand(self, demand_id: int) -> MadeItemDemandItem:
        """Lets the lifecycle reconciler store what the demand's facts
        derive, as a use case does after each change, and returns the demand
        as stored then. The seed stores every demand allocated before any of
        its allocations exist, so its stored status is expected to move."""
        await give_demand_facts(self.db, LifecycleAggregate.MADE_DEMANDS, demand_id, exact=False)
        await self.db.commit()
        demand = await SqlAlchemyMadeItemDemandItemRepository(self.db).get_by_id(demand_id)
        assert demand is not None
        return demand

    @_memo
    async def made_allocation(self) -> MadeItemDemandAllocation:
        demand = await self.made_demand()
        lot = await self.lot()
        await self.internal_position()
        saved = await SqlAlchemyMadeItemAllocationRepository(self.db).save(
            make(MadeItemDemandAllocation, demand_item_id=demand.id, lot_id=lot.id, quantity=5.0)
        )
        await self.db.commit()
        self._cache["made_demand"] = await self._settled_made_demand(demand.id)
        return saved

    @_memo
    async def bought_demand(self) -> BoughtItemDemandItem:
        item = await self.bought_item()
        bucket = await self.bought_bucket()
        saved = await SqlAlchemyBoughtItemDemandItemRepository(self.db).save(
            make(
                BoughtItemDemandItem,
                item_id=item.id,
                bucket_id=bucket.id,
                status=BoughtItemDemandStatus.ALLOCATED,
                **await self._demand_fields(),
            )
        )
        await self.db.commit()
        return await self._settled_bought_demand(saved.id)

    async def _settled_bought_demand(self, demand_id: int) -> BoughtItemDemandItem:
        """See _settled_made_demand."""
        await give_demand_facts(self.db, LifecycleAggregate.BOUGHT_DEMANDS, demand_id, exact=False)
        await self.db.commit()
        demand = await SqlAlchemyBoughtItemDemandItemRepository(self.db).get_by_id(demand_id)
        assert demand is not None
        return demand

    @_memo
    async def bought_allocation(self) -> BoughtItemDemandAllocation:
        demand = await self.bought_demand()
        item = await self.bought_order_item()
        saved = await SqlAlchemyBoughtItemAllocationRepository(self.db).save(
            make(
                BoughtItemDemandAllocation,
                demand_item_id=demand.id,
                order_item_id=item.id,
                quantity=5.0,
            )
        )
        await self.db.commit()
        self._cache["bought_demand"] = await self._settled_bought_demand(demand.id)
        return saved

    @_memo
    async def source_demand(self) -> SourceItemDemandItem:
        """The lot's raw-material demand, linked both ways: the demand
        names its lot and the lot names the demand as its input."""
        item = await self.source_item()
        bucket = await self.source_bucket()
        lot = await self.lot()
        demand = await SqlAlchemySourceItemDemandRepository(self.db).save(
            make(
                SourceItemDemandItem,
                bought_item_id=None,
                source_item_id=item.id,
                lot_id=lot.id,
                bucket_id=bucket.id,
                status=SourceItemDemandStatus.ALLOCATED,
                **await self._demand_fields(),
            )
        )
        lot.input_demand_id = demand.id
        self._cache["lot"] = await SqlAlchemyProductionLotRepository(self.db).save(lot)
        await self.db.commit()
        return await self._settled_source_demand(demand.id)

    async def _settled_source_demand(self, demand_id: int) -> SourceItemDemandItem:
        """See _settled_made_demand."""
        await give_demand_facts(self.db, LifecycleAggregate.SOURCE_DEMANDS, demand_id, exact=False)
        await self.db.commit()
        demand = await SqlAlchemySourceItemDemandRepository(self.db).get_by_id(demand_id)
        assert demand is not None
        return demand

    @_memo
    async def source_allocation(self) -> SourceItemDemandAllocation:
        demand = await self.source_demand()
        item = await self.source_order_item()
        saved = await SqlAlchemySourceItemAllocationRepository(self.db).save(
            make(
                SourceItemDemandAllocation,
                demand_item_id=demand.id,
                order_item_id=item.id,
                quantity=5.0,
            )
        )
        await self.db.commit()
        self._cache["source_demand"] = await self._settled_source_demand(demand.id)
        return saved

    @_memo
    async def printer(self) -> Printer:
        item = await self.bought_item()
        saved = await SqlAlchemyPrinterRepository(self.db).save(
            make(
                Printer,
                name="Label printer",
                kind=PrinterKind.ZPL_LABEL,
                host="printer.local",
                port=9100,
                transport="raw",
                bought_item_ids=[item.id],
                enabled=True,
                creator_id=self.uid,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def print_template(self) -> PrintTemplate:
        """Templates are created as slots at startup and only ever edited, so
        the row is inserted directly and then armed through the repository."""
        printer = await self.printer()
        self.db.add(
            PrintTemplateOrmModel(created=TODAY, classifier="lot_label", creator_id=self.uid)
        )
        await self.db.commit()
        repo = SqlAlchemyPrintTemplateRepository(self.db)
        template = await repo.get_by_classifier("lot_label")
        assert template is not None
        saved = await repo.save(
            dataclasses.replace(
                template, trigger=PrintTrigger.LOT_CREATED, auto_print=True, printer_id=printer.id
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def calculation(self) -> Calculation:
        """A released project calculation. Its number follows the default
        format and ends in "1" like every other seeded number."""
        saved = await SqlAlchemyCalculationRepository(self.db).save(
            make(
                Calculation,
                document_number="CAL-26-0001",
                tool="fit_calculator",
                title="Bearing seat",
                project_id=(await self.project()).id,
                creator_id=self.uid,
                released_at=NOW,
                released_by_id=self.other_user.id,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def checklist(self) -> Checklist:
        """A released project checklist, numbered like the calculation."""
        saved = await SqlAlchemyChecklistRepository(self.db).save(
            make(
                Checklist,
                document_number="CHK-26-0001",
                type="hydraulics",
                title="Press hydraulics",
                verdict=ChecklistVerdict.PASSED,
                project_id=(await self.project()).id,
                creator_id=self.uid,
                released_at=NOW,
                released_by_id=self.other_user.id,
            )
        )
        await self.db.commit()
        return saved

    async def _device_option(
        self, category: ProductDeviceOptionCategory, label: str, letter: str | None = None
    ) -> ProductDeviceOption:
        saved = await SqlAlchemyProductDeviceOptionRepository(self.db).save(
            make(
                ProductDeviceOption,
                category=category,
                label=LocalizedText({"enGB": label}),
                letter=letter,
                creator_id=self.uid,
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def driving_medium(self) -> ProductDeviceOption:
        return await self._device_option(
            ProductDeviceOptionCategory.DRIVING_MEDIUM, "Pneumatic", letter="P"
        )

    @_memo
    async def component_role(self) -> ProductDeviceOption:
        return await self._device_option(ProductDeviceOptionCategory.COMPONENT_ROLE, "Valve")

    @_memo
    async def energy_behaviour(self) -> ProductDeviceOption:
        return await self._device_option(ProductDeviceOptionCategory.ENERGY_BEHAVIOUR, "Hold")

    @_memo
    async def device_kind(self) -> ProductDeviceKind:
        """A kind with one position and one parameter, so both child
        collections load."""
        saved = await SqlAlchemyProductDeviceKindRepository(self.db).save(
            make(
                ProductDeviceKind,
                label=LocalizedText({"enGB": "Cylinder"}),
                creator_id=self.uid,
                positions=[
                    make(
                        ProductDeviceKindPosition,
                        kind_id=0,
                        label=LocalizedText({"enGB": "Retracted"}),
                    )
                ],
                parameters=[
                    make(
                        ProductDeviceKindParameter,
                        kind_id=0,
                        label=LocalizedText({"enGB": "Stroke"}),
                        value_type=ProductDeviceParameterType.NUMBER,
                    )
                ],
            )
        )
        await self.db.commit()
        return saved

    async def _device_image(self, category: ProductFileCategory) -> ProductFile:
        saved = await SqlAlchemyProductFileRepository(self.db).save(
            make(
                ProductFile,
                product_id=(await self.product()).id,
                category=category,
                uploaded_by_user_id=self.uid,
                **file_fields("device"),
            )
        )
        await self.db.commit()
        return saved

    @_memo
    async def product_device(self) -> ProductDevice:
        """A device with its initial position, both energy behaviours, both
        images and a component on a bought item, so every optional link of
        the device and its component is set."""
        product = await self.product()
        medium = await self.driving_medium()
        kind = await self.device_kind()
        behaviour = await self.energy_behaviour()
        saved = await SqlAlchemyProductDeviceRepository(self.db).save(
            make(
                ProductDevice,
                product_id=product.id,
                name="Cylinder",
                driving_medium_id=medium.id,
                number=1,
                name_utf8="Cylinder P1",
                name_ascii="Cylinder P1",
                name_ascii_key="cylinder p1",
                group_key="cylinder p",
                kind_id=kind.id,
                creator_id=self.uid,
                initial_position_id=kind.positions[0].id,
                energy_loss_behaviour_id=behaviour.id,
                energy_restoration_behaviour_id=behaviour.id,
                rendering_file_id=(
                    await self._device_image(ProductFileCategory.DEVICE_RENDERING)
                ).id,
                assembly_file_id=(await self._device_image(ProductFileCategory.DEVICE_ASSEMBLY)).id,
                components=[
                    make(
                        ProductDeviceComponent,
                        device_id=0,
                        product_id=product.id,
                        role_id=(await self.component_role()).id,
                        bought_item_id=(await self.bought_item()).id,
                        eplan_tag="-MB1",
                    )
                ],
            )
        )
        await self.db.commit()
        return saved

    async def full_lot(self) -> ProductionLot:
        """The lot with everything that hangs off it: both position kinds,
        their steps, an order item on the external one, a production order
        on the internal one, a provision, an event, its raw-material demand
        with an allocation, and a made-item demand it covers."""
        await self.source_allocation()
        await self.made_order_item()
        await self.production_order()
        await self.provision()
        await self.lot_event()
        await self.made_allocation()
        await self.follow_up_lots()
        return await self.lot()
