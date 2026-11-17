"""
Unit tests for ApproveLotSource's optional write-back of an approved lot's
source item onto its made item's MadeItem.source_item_id, gated by the
AdminProductionSettings.assign_approved_material_to_item /
overwrite_item_material_on_approval flags (see approve_lot_source.py and
material_source_rules.resolve_made_item_source_assignment). No database,
no HTTP.

Fakes and helpers are reused from the existing unit test modules rather
than duplicated wholesale, following the same cross-file-import precedent
test_lot_source_approval_use_cases.py already establishes. See that file
for make_lot/ApprovalSettingsRepo, and tests/unit/production_lot/
(fakes.py, _helpers.py) for the repository fakes and entity builders.
FakeMadeItemRepository.save raises NotImplementedError in the
shared fixture file, so this file subclasses it locally with a recording
version rather than editing that read-only file.
"""

import pytest

from src.modules.catalogue.application.facade.made_item_material_source import (
    MadeItemMaterialSources,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import SourceItemInactiveError
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.fulfillment.application.use_cases.production_lot.approve_lot_source import (
    ApproveLotSource,
)
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_source_item
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeSourceItemRepository
from tests.unit.test_lot_source_approval_use_cases import ApprovalSettingsRepo
from tests.unit.test_lot_source_approval_use_cases import make_lot

# ── Fakes / helpers local to this file ──────────────────────────────────


class RecordingMadeItemRepository(FakeMadeItemRepository):
    """FakeMadeItemRepository.save raises NotImplementedError;
    this subclass records what was saved instead, so tests can assert on
    both the mutated entity and that save was (or wasn't)
    called."""

    def __init__(self, items: list[MadeItem]) -> None:
        super().__init__(items)
        self.saved: list[MadeItem] = []

    async def save(self, item: MadeItem) -> MadeItem:
        self._items[item.id] = item
        self.saved.append(item)
        return item


class MaterialAssignmentSettingsRepo(ApprovalSettingsRepo):
    """ApprovalSettingsRepo (test_lot_source_approval_use_cases.py) only
    controls require_source_item_approval; this subclass adds control over
    the two write-back flags without touching that file."""

    def __init__(
        self,
        assign_approved_material_to_item: bool = False,
        overwrite_item_material_on_approval: bool = False,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._assign = assign_approved_material_to_item
        self._overwrite = overwrite_item_material_on_approval

    async def get_production(self):
        settings = await super().get_production()
        settings.assign_approved_material_to_item = self._assign
        settings.overwrite_item_material_on_approval = self._overwrite
        return settings


# ── Tests ────────────────────────────────────────────────────────────────


class TestApproveLotSourceMaterialAssignment:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.demand_repo = FakeSourceItemDemandRepository()
        self.uow = FakeUnitOfWork()
        # Only manage:lots, no write:made_items. The write-back runs on
        # manage:lots alone.
        self.actor = make_user(permissions=[Permission.MANAGE_LOTS])

    def _use_case(
        self,
        made_item_repo=None,
        source_item_repo=None,
        settings_repo=None,
    ) -> ApproveLotSource:
        return ApproveLotSource(
            lot_repo=self.lot_repo,
            source_item_demand_repo=self.demand_repo,
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
            project_repo=FakeProjectRepository(),
            made_items=MadeItemMaterialSources(made_item_repo),
            source_item_repo=source_item_repo or FakeSourceItemRepository([make_source_item(id=1)]),
            settings_repo=settings_repo,
        )

    # ── Assigned ─────────────────────────────────────────────────────

    async def test_assigned_updates_made_item_sets_changed_by_and_changelogs(self):
        made_item = make_made_item(id=1, source_item_id=None)
        made_item_repo = RecordingMadeItemRepository([made_item])
        source_item_repo = FakeSourceItemRepository(
            [make_source_item(id=1, status=SourceItemCatalogueStatus.ACTIVE)]
        )
        settings_repo = MaterialAssignmentSettingsRepo(assign_approved_material_to_item=True)

        lot = await self.lot_repo.save(make_lot(made_item_id=1, source_item_id=1))
        use_case = self._use_case(made_item_repo, source_item_repo, settings_repo)
        result = await use_case.execute(self.actor, lot.id)

        assert result.input_demand_id is not None
        assert len(made_item_repo.saved) == 1
        saved_made_item = made_item_repo.saved[0]
        assert saved_made_item.source_item_id == 1
        assert saved_made_item.changed_by_id == self.actor.id
        assert saved_made_item.changed is not None
        assert any(
            "material source set to source item #1" in c.lower() for c in saved_made_item.changes
        )

        saved_lot = await self.lot_repo.get_by_id(lot.id)
        assert any(
            "assigned approved material to made item #1" in c.lower() for c in saved_lot.changes
        )

        events = await self.lot_repo.get_events(lot.id)
        assert len(events) == 1
        assert events[0].event_type == LotEventType.LOT_SOURCE_APPROVED
        assert events[0].payload["made_item_id"] == 1
        assert events[0].payload["made_item_source_assignment"] == "assigned"

    async def test_manage_lots_only_actor_still_triggers_the_write(self):
        """No write:made_items check. self.actor already
        carries only manage:lots (see setup_method); this test makes that
        assertion explicit rather than relying on it implicitly."""
        assert not self.actor.has_permission(Permission.WRITE_MADE_ITEMS)

        made_item = make_made_item(id=1, source_item_id=None)
        made_item_repo = RecordingMadeItemRepository([made_item])
        source_item_repo = FakeSourceItemRepository(
            [make_source_item(id=1, status=SourceItemCatalogueStatus.ACTIVE)]
        )
        settings_repo = MaterialAssignmentSettingsRepo(assign_approved_material_to_item=True)

        lot = await self.lot_repo.save(make_lot(made_item_id=1, source_item_id=1))
        await self._use_case(made_item_repo, source_item_repo, settings_repo).execute(
            self.actor, lot.id
        )

        assert len(made_item_repo.saved) == 1
        assert made_item_repo.saved[0].source_item_id == 1

    async def test_overwrite_on_replaces_a_different_existing_source_item(self):
        made_item = make_made_item(id=1, source_item_id=2)
        made_item_repo = RecordingMadeItemRepository([made_item])
        source_item_repo = FakeSourceItemRepository(
            [make_source_item(id=1, status=SourceItemCatalogueStatus.ACTIVE)]
        )
        settings_repo = MaterialAssignmentSettingsRepo(
            assign_approved_material_to_item=True, overwrite_item_material_on_approval=True
        )

        lot = await self.lot_repo.save(make_lot(made_item_id=1, source_item_id=1))
        result = await self._use_case(made_item_repo, source_item_repo, settings_repo).execute(
            self.actor, lot.id
        )

        assert result.input_demand_id is not None
        assert len(made_item_repo.saved) == 1
        assert made_item_repo.saved[0].source_item_id == 1

    # ── Skip branches: approval + demand always succeed, made item untouched ──

    async def test_disabled_setting_skips_and_approval_still_succeeds(self):
        made_item = make_made_item(id=1, source_item_id=None)
        made_item_repo = RecordingMadeItemRepository([made_item])
        source_item_repo = FakeSourceItemRepository(
            [make_source_item(id=1, status=SourceItemCatalogueStatus.ACTIVE)]
        )
        settings_repo = MaterialAssignmentSettingsRepo(assign_approved_material_to_item=False)

        lot = await self.lot_repo.save(make_lot(made_item_id=1, source_item_id=1))
        result = await self._use_case(made_item_repo, source_item_repo, settings_repo).execute(
            self.actor, lot.id
        )

        assert result.source_approval_status == "approved"
        assert result.input_demand_id is not None
        assert made_item_repo.saved == []
        assert made_item.source_item_id is None

        events = await self.lot_repo.get_events(lot.id)
        assert events[0].payload["made_item_source_assignment"] == "skipped_disabled"

    async def test_bought_item_present_skips_and_approval_still_succeeds(self):
        made_item = make_made_item(id=1, bought_item_id=99)
        made_item_repo = RecordingMadeItemRepository([made_item])
        source_item_repo = FakeSourceItemRepository(
            [make_source_item(id=1, status=SourceItemCatalogueStatus.ACTIVE)]
        )
        settings_repo = MaterialAssignmentSettingsRepo(
            assign_approved_material_to_item=True, overwrite_item_material_on_approval=True
        )

        lot = await self.lot_repo.save(make_lot(made_item_id=1, source_item_id=1))
        result = await self._use_case(made_item_repo, source_item_repo, settings_repo).execute(
            self.actor, lot.id
        )

        assert result.source_approval_status == "approved"
        assert result.input_demand_id is not None
        assert made_item_repo.saved == []
        assert made_item.source_item_id is None
        assert made_item.bought_item_id == 99

        events = await self.lot_repo.get_events(lot.id)
        assert events[0].payload["made_item_source_assignment"] == "skipped_bought_item"

    async def test_existing_source_with_overwrite_off_skips_and_approval_still_succeeds(self):
        made_item = make_made_item(id=1, source_item_id=2)
        made_item_repo = RecordingMadeItemRepository([made_item])
        source_item_repo = FakeSourceItemRepository(
            [make_source_item(id=1, status=SourceItemCatalogueStatus.ACTIVE)]
        )
        settings_repo = MaterialAssignmentSettingsRepo(
            assign_approved_material_to_item=True, overwrite_item_material_on_approval=False
        )

        lot = await self.lot_repo.save(make_lot(made_item_id=1, source_item_id=1))
        result = await self._use_case(made_item_repo, source_item_repo, settings_repo).execute(
            self.actor, lot.id
        )

        assert result.source_approval_status == "approved"
        assert result.input_demand_id is not None
        assert made_item_repo.saved == []
        assert made_item.source_item_id == 2

        events = await self.lot_repo.get_events(lot.id)
        assert events[0].payload["made_item_source_assignment"] == "skipped_existing_source"

    async def test_inactive_source_item_refuses_the_approval_before_any_write_back(self):
        made_item = make_made_item(id=1, source_item_id=None)
        made_item_repo = RecordingMadeItemRepository([made_item])
        source_item_repo = FakeSourceItemRepository(
            [make_source_item(id=1, status=SourceItemCatalogueStatus.INACTIVE)]
        )
        settings_repo = MaterialAssignmentSettingsRepo(assign_approved_material_to_item=True)

        lot = await self.lot_repo.save(make_lot(made_item_id=1, source_item_id=1))
        with pytest.raises(SourceItemInactiveError):
            await self._use_case(made_item_repo, source_item_repo, settings_repo).execute(
                self.actor, lot.id
            )

        assert made_item_repo.saved == []
        assert made_item.source_item_id is None
        assert len(self.demand_repo.demands) == 0

    # ── Back-compat: 3-arg construction ─────────────────────────────

    async def test_three_arg_construction_still_approves_and_records_skipped_disabled(self):
        use_case = ApproveLotSource(
            lot_repo=self.lot_repo,
            source_item_demand_repo=self.demand_repo,
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
            project_repo=FakeProjectRepository(),
            source_item_repo=FakeSourceItemRepository([make_source_item(id=1)]),
        )
        lot = await self.lot_repo.save(make_lot(made_item_id=1, source_item_id=1))
        result = await use_case.execute(self.actor, lot.id)

        assert result.source_approval_status == "approved"
        assert result.input_demand_id is not None

        events = await self.lot_repo.get_events(lot.id)
        assert events[0].payload["made_item_source_assignment"] == "skipped_disabled"
        assert events[0].payload["made_item_id"] == 1
