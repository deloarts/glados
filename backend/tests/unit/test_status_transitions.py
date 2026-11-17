"""
The `default()` and `values()` classmethods and the other helpers of the
status value objects. Which statuses follow which is decided by the
derivation and intent tables of src/domain/services/lifecycle/, tested in
tests/unit/lifecycle/.
"""

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ComplexityClass
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)

# ── The three demand status enums ─────────────────────────────────────
# BoughtItemDemandStatus, SourceItemDemandStatus and MadeItemDemandStatus
# share their values; these tests assert that rather than assuming it.

DEMAND_STATUS_ENUMS = [BoughtItemDemandStatus, SourceItemDemandStatus, MadeItemDemandStatus]


@pytest.mark.parametrize("enum_cls", DEMAND_STATUS_ENUMS, ids=lambda c: c.__name__)
class TestDemandStatusEnums:
    def test_default_is_open(self, enum_cls):
        assert enum_cls.default() == enum_cls.OPEN

    def test_values_lists_all_five_states(self, enum_cls):
        assert enum_cls.values() == ["open", "allocated", "ordered", "fulfilled", "canceled"]


# ── ProductionOrderStatus ─────────────────────────────────────────────


class TestProductionOrderStatus:
    def test_default_is_queued(self):
        assert ProductionOrderStatus.default() == ProductionOrderStatus.QUEUED

    def test_values_lists_all_five_states(self):
        assert ProductionOrderStatus.values() == [
            "queued",
            "in_progress",
            "paused",
            "completed",
            "canceled",
        ]


# ── LotStatus ─────────────────────────────────────────────────────────


class TestLotStatus:
    def test_default_is_draft(self):
        assert LotStatus.default() == LotStatus.DRAFT

    def test_values_lists_all_eight_states(self):
        assert LotStatus.values() == [
            "draft",
            "partially_planned",
            "planned",
            "in_progress",
            "on_hold",
            "completed",
            "canceled",
            "scrapped",
        ]


# ── Simple catalogue / classification enums ───────────────────────────


class TestSimpleEnumDefaults:
    def test_bought_item_catalogue_status(self):
        assert BoughtItemCatalogueStatus.default() == BoughtItemCatalogueStatus.ACTIVE

    def test_made_item_catalogue_status(self):
        assert MadeItemCatalogueStatus.default() == MadeItemCatalogueStatus.ACTIVE

    def test_source_item_catalogue_status(self):
        assert SourceItemCatalogueStatus.default() == SourceItemCatalogueStatus.ACTIVE

    def test_the_three_catalogue_status_enums_share_the_same_members(self):
        members = {"active", "inactive", "replaced"}
        assert {s.value for s in BoughtItemCatalogueStatus} == members
        assert {s.value for s in MadeItemCatalogueStatus} == members
        assert {s.value for s in SourceItemCatalogueStatus} == members

    def test_allocation_sources(self):
        assert AllocationSource.default() == AllocationSource.ORDER
        assert SourceItemAllocationSource.default() == SourceItemAllocationSource.ORDER
        assert MadeItemAllocationSource.default() == MadeItemAllocationSource.LOT

    def test_made_item_allocation_source_defaults_to_lot_not_order(self):
        """MadeItem demand is covered by a ProductionLot, not a purchase
        order, the one place this trio deliberately differs."""
        assert MadeItemAllocationSource.default().value == "lot"

    def test_order_status(self):
        assert OrderStatus.default() == OrderStatus.DRAFT
        assert OrderStatus.values() == [
            "draft",
            "requested",
            "partially_ordered",
            "ordered",
            "partially_delivered",
            "delivered",
            "canceled",
        ]

    def test_order_item_status(self):
        assert OrderItemStatus.default() == OrderItemStatus.PENDING
        assert OrderItemStatus.values() == [
            "pending",
            "requested",
            "ordered",
            "partially_delivered",
            "delivered",
            "canceled",
        ]

    def test_order_status_and_order_item_status_differ_in_first_state_and_partly_ordered(self):
        """An order is partly ordered while some of its lines are ordered and
        others are not; a single line has no such state."""
        assert OrderStatus.values()[0] == "draft"
        assert OrderItemStatus.values()[0] == "pending"
        order_rest = [v for v in OrderStatus.values()[1:] if v != "partially_ordered"]
        assert order_rest == OrderItemStatus.values()[1:]

    def test_order_line_type(self):
        assert OrderLineType.default() == OrderLineType.BOUGHT
        assert {t.value for t in OrderLineType} == {"BOUGHT", "MADE", "SOURCE", "VIRTUAL"}

    def test_urgency_class(self):
        assert UrgencyClass.default() == UrgencyClass.NORMAL
        assert UrgencyClass.values() == ["low", "normal", "high", "critical"]

    def test_complexity_class(self):
        assert ComplexityClass.default() == ComplexityClass.NORMAL
        assert ComplexityClass.values() == ["low", "normal", "very"]

    def test_supplier_level_defaults_to_b_not_a(self):
        assert SupplierLevel.default() == SupplierLevel.B
        assert SupplierLevel.values() == ["A", "B", "C"]

    def test_data_source(self):
        assert DataSource.default() == DataSource.WEB
        assert DataSource.values() == ["WEB", "CAD"]

    def test_schedule_conflict_reason_values(self):
        values = ScheduleConflictReason.values()
        assert len(values) == 15
        assert "no_working_time" in values
        assert "window_overlap" in values
        assert "window_before_predecessor" in values
        assert "chain_cycle" in values
        assert "no_machine_assigned" in values
        assert "capability_mismatch" in values
        assert "waiting_on_material" in values
        assert values == [r.value for r in ScheduleConflictReason]


# ── BoughtItemFileCategory singleton logic ────────────────────────────


class TestBoughtItemFileCategory:
    def test_singletons_include_the_drawing_slots(self):
        """DRAWING/DXF are singletons, mirroring MadeItemFileCategory
        (application.use_cases.pdm.pdm_documents.PdmDocumentSync needs the same
        category names on both item families)."""
        assert BoughtItemFileCategory.singletons() == {
            BoughtItemFileCategory.STEP,
            BoughtItemFileCategory.MESH,
            BoughtItemFileCategory.DRAWING,
            BoughtItemFileCategory.DXF,
        }

    @pytest.mark.parametrize(
        "category",
        [
            BoughtItemFileCategory.STEP,
            BoughtItemFileCategory.MESH,
            BoughtItemFileCategory.DRAWING,
            BoughtItemFileCategory.DXF,
        ],
    )
    def test_singleton_categories_report_true(self, category):
        assert category.is_singleton() is True

    def test_pdf_is_the_only_multi_upload_category(self):
        assert BoughtItemFileCategory.PDF.is_singleton() is False

    def test_every_category_is_either_singleton_or_pdf(self):
        non_singletons = [c for c in BoughtItemFileCategory if not c.is_singleton()]
        assert non_singletons == [BoughtItemFileCategory.PDF]


# ── MadeItemFileCategory singleton logic ──────────────────────────────


class TestMadeItemFileCategory:
    def test_singletons_include_the_drawing_slots(self):
        assert MadeItemFileCategory.singletons() == {
            MadeItemFileCategory.STEP,
            MadeItemFileCategory.MESH,
            MadeItemFileCategory.DRAWING,
            MadeItemFileCategory.DXF,
        }

    @pytest.mark.parametrize(
        "category",
        [
            MadeItemFileCategory.STEP,
            MadeItemFileCategory.MESH,
            MadeItemFileCategory.DRAWING,
            MadeItemFileCategory.DXF,
        ],
    )
    def test_singleton_categories_report_true(self, category):
        assert category.is_singleton() is True

    def test_pdf_is_the_only_multi_upload_category(self):
        assert MadeItemFileCategory.PDF.is_singleton() is False

    def test_every_category_is_either_singleton_or_pdf(self):
        non_singletons = [c for c in MadeItemFileCategory if not c.is_singleton()]
        assert non_singletons == [MadeItemFileCategory.PDF]

    def test_mirrors_bought_item_categories_exactly(self):
        """BoughtItemFileCategory has the same DRAWING/DXF slots (used by
        the PDM `documents` watched folder), so the two families' category
        sets are identical. See this class's sibling test in
        TestBoughtItemFileCategory."""
        made = {c.value for c in MadeItemFileCategory}
        bought = {c.value for c in BoughtItemFileCategory}
        assert made == bought
