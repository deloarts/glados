"""
Unit tests for source item catalogue use cases (create, update, delete, get).
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.modules.catalogue.application.dto.source_item_dto import CreateSourceItemCommand
from src.modules.catalogue.application.dto.source_item_dto import UpdateSourceItemCommand
from src.modules.catalogue.application.use_cases.source_item.archive_source_item import (
    ArchiveSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.create_source_item import (
    CreateSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.get_source_item import GetSourceItem
from src.modules.catalogue.application.use_cases.source_item.get_source_item import GetSourceItems
from src.modules.catalogue.application.use_cases.source_item.restore_source_item import (
    RestoreSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.update_source_item import (
    UpdateSourceItem,
)
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.errors import SourceItemDuplicateSpecError
from src.modules.catalogue.domain.errors import SourceItemInactiveError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.errors import SourceItemTypeNotFoundError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_supplier(id: int = 1, name: str = "Acme") -> Supplier:
    return Supplier(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name=name,
        legal_name=None,
        vat_id=None,
        level=SupplierLevel.B,
        capability_ids=[],
        article_group_ids=[],
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        order_email=None,
        order_language=None,
        order_template=None,
        request_email=None,
        request_language=None,
        request_template=None,
        creator_id=1,
    )


def make_source_item(
    id: int = 1,
    status: SourceItemCatalogueStatus = SourceItemCatalogueStatus.ACTIVE,
    type_id: int = 1,
    archived: bool = False,
) -> SourceItem:
    return SourceItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        type_id=type_id,
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


def make_source_item_type(id: int = 1, name: str = "Round bar") -> SourceItemType:
    return SourceItemType(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name=name,
        label_color="#999999",
        label_font_color="#000000",
        description="",
        creator_id=1,
    )


class FakeSourceItemRepository:
    def __init__(self, items: list[SourceItem] | None = None):
        self._items: dict[int, SourceItem] = {}
        self._next_id = 1
        for i in items or []:
            self._items[i.id] = i
            self._next_id = max(self._next_id, i.id + 1)

    async def get_by_id(self, id: int) -> SourceItem | None:
        return self._items.get(id)

    async def lock_for_update(self, id: int) -> None:
        return None

    async def get_by_spec_candidates(
        self,
        type_id: int,
        material: str,
        manufacturer_id: int | None,
    ) -> list[SourceItem]:
        return [
            item
            for item in self._items.values()
            if item.type_id == type_id
            and item.material == material
            and item.manufacturer_id == manufacturer_id
            and not item.archived
        ]

    async def get_multi(self, filters: SourceItemFilterDto) -> tuple[int, list[SourceItem]]:
        items = list(self._items.values())
        if not filters.include_archived:
            items = [i for i in items if not i.archived]
        return len(items), items

    async def save(self, item: SourceItem) -> SourceItem:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._items[item.id] = item
        return item

    async def delete(self, item: SourceItem) -> None:
        raise NotImplementedError


class FakeSupplierRepository:
    def __init__(self, suppliers: list[Supplier] | None = None):
        self._suppliers: dict[int, Supplier] = {s.id: s for s in (suppliers or [])}

    async def get_by_id(self, id: int) -> Supplier | None:
        return self._suppliers.get(id)


class FakeSourceItemTypeRepository:
    def __init__(self, types: list[SourceItemType] | None = None):
        self._types: dict[int, SourceItemType] = {t.id: t for t in (types or [])}

    async def get_by_id(self, id: int) -> SourceItemType | None:
        return self._types.get(id)


# ── CreateSourceItem ────────────────────────────────────────────────────


class TestCreateSourceItem:
    def setup_method(self):
        self.source_item_repo = FakeSourceItemRepository()
        self.supplier_repo = FakeSupplierRepository([make_supplier(id=1)])
        self.source_item_type_repo = FakeSourceItemTypeRepository([make_source_item_type(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEMS])
        self.use_case = CreateSourceItem(
            self.source_item_repo,
            self.supplier_repo,
            self.source_item_type_repo,
            uow=FakeUnitOfWork(),
        )

    def _cmd(self, **kwargs) -> CreateSourceItemCommand:
        defaults = dict(type_id=1, dimension="40mm", material="1.0037")
        defaults.update(kwargs)
        return CreateSourceItemCommand(**defaults)

    async def test_creates_standalone_item_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.type_id == 1
        assert result.id > 0

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_missing_manufacturer_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(manufacturer_id=999))

    async def test_missing_type_raises(self):
        with pytest.raises(SourceItemTypeNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(type_id=999))

    async def test_creates_with_manufacturer(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(manufacturer_id=1))
        assert result.manufacturer_id == 1

    async def test_duplicate_spec_without_manufacturer_rejected(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        with pytest.raises(SourceItemDuplicateSpecError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd())

    async def test_duplicate_spec_with_manufacturer_rejected(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(manufacturer_id=1))
        with pytest.raises(SourceItemDuplicateSpecError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(manufacturer_id=1))

    async def test_same_spec_with_different_manufacturer_is_allowed(self):
        self.supplier_repo._suppliers[2] = make_supplier(id=2, name="Other")
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(manufacturer_id=1))
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(manufacturer_id=2))
        assert result.manufacturer_id == 2

    async def test_same_spec_without_manufacturer_does_not_conflict_with_manufacturer_variant(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(manufacturer_id=1))
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.manufacturer_id is None

    async def test_permuted_box_dimension_is_treated_as_duplicate(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(dimension="100 × 200 × 20"))
        with pytest.raises(SourceItemDuplicateSpecError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(dimension="200 × 100 × 20"))

    async def test_decimal_formatting_variant_is_treated_as_duplicate(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(dimension="100.0 × 200 × 20"))
        with pytest.raises(SourceItemDuplicateSpecError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(dimension="100 × 200 × 20"))

    async def test_permuted_dimension_with_different_manufacturer_is_allowed(self):
        await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(dimension="100 × 200 × 20", manufacturer_id=1)
        )
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(dimension="200 × 100 × 20")
        )
        assert result.manufacturer_id is None

    async def test_create_persists_order_codes(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(order_code_1="ACME-1", order_code_2="ACME-1-ALT"),
        )
        assert result.order_code_1 == "ACME-1"
        assert result.order_code_2 == "ACME-1-ALT"

    async def test_order_codes_are_not_part_of_duplicate_identity(self):
        """Two items with the identical dimension/type/material/manufacturer
        spec but different order codes are still duplicates: order codes
        are supplier metadata, not spec identity."""
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(order_code_1="ACME-1"))
        with pytest.raises(SourceItemDuplicateSpecError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(order_code_1="ACME-2"))


# ── UpdateSourceItem ────────────────────────────────────────────────────


class TestUpdateSourceItem:
    def setup_method(self):
        self.item = make_source_item(id=1)
        self.source_item_repo = FakeSourceItemRepository([self.item])
        self.supplier_repo = FakeSupplierRepository([make_supplier(id=1)])
        self.source_item_type_repo = FakeSourceItemTypeRepository([make_source_item_type(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEMS])
        self.use_case = UpdateSourceItem(
            self.source_item_repo,
            self.supplier_repo,
            self.source_item_type_repo,
            uow=FakeUnitOfWork(),
        )

    def _cmd(self, **kwargs) -> UpdateSourceItemCommand:
        defaults = dict(type_id=1, dimension="40mm", material="1.0037")
        defaults.update(kwargs)
        return UpdateSourceItemCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(dimension="50mm")
        )
        assert result.dimension == "50mm"

    async def test_not_found_raises(self):
        with pytest.raises(SourceItemNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, item_id=1, cmd=self._cmd())

    async def test_missing_manufacturer_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(manufacturer_id=999)
            )

    async def test_missing_type_raises(self):
        with pytest.raises(SourceItemTypeNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(type_id=999))

    async def test_updating_own_spec_unchanged_is_allowed(self):
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(material="1.0037")
        )
        assert result.id == 1

    async def test_no_spurious_changelog_entry_when_order_codes_are_untouched(self):
        """Regression guard: the `old` dict passed to diff_changes() must
        list order_code_1/2 alongside every other field it tracks, or their
        constant None → None reads as a change on every unrelated save."""
        result = await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())
        latest_entry = result.changes[-1]
        assert "No changes." in latest_entry
        assert "order_code" not in latest_entry

    async def test_changing_an_order_code_is_reflected_in_the_changelog(self):
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(order_code_1="ACME-1")
        )
        assert result.order_code_1 == "ACME-1"
        assert "order_code_1" in result.changes[-1]

    async def test_duplicate_spec_of_another_item_rejected(self):
        other = make_source_item(id=2)
        other.dimension = "50mm"
        self.source_item_repo._items[2] = other
        with pytest.raises(SourceItemDuplicateSpecError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(dimension="50mm", material="1.0037")
            )

    async def test_update_to_permuted_duplicate_of_another_item_rejected(self):
        other = make_source_item(id=2)
        other.dimension = "100 × 200 × 20"
        self.source_item_repo._items[2] = other
        with pytest.raises(SourceItemDuplicateSpecError):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                cmd=self._cmd(dimension="200 × 100 × 20", material="1.0037"),
            )


# ── CreateSourceItemCommand / UpdateSourceItemCommand validation ──────────


class TestSourceItemCommandRequiredFields:
    def test_create_requires_type_id(self):
        with pytest.raises(ValidationError):
            CreateSourceItemCommand(dimension="40mm", material="1.0037")

    def test_create_requires_material(self):
        with pytest.raises(ValidationError):
            CreateSourceItemCommand(type_id=1, dimension="40mm")

    def test_update_requires_type_id(self):
        with pytest.raises(ValidationError):
            UpdateSourceItemCommand(dimension="40mm", material="1.0037")

    def test_update_requires_material(self):
        with pytest.raises(ValidationError):
            UpdateSourceItemCommand(type_id=1, dimension="40mm")


# ── ArchiveSourceItem / RestoreSourceItem ───────────────────────────────


class TestArchiveSourceItem:
    def setup_method(self):
        self.item = make_source_item(id=1)
        self.source_item_repo = FakeSourceItemRepository([self.item])
        self.actor = make_user(permissions=[Permission.DELETE_SOURCE_ITEMS])
        self.use_case = ArchiveSourceItem(self.source_item_repo, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, item_id=1)
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(SourceItemNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEMS])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, item_id=1)


class TestRestoreSourceItem:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.DELETE_SOURCE_ITEMS])

    async def test_restores_successfully(self):
        item = make_source_item(id=1, archived=True)
        repo = FakeSourceItemRepository([item])
        result = await RestoreSourceItem(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, item_id=1
        )
        assert result.archived is False

    async def test_restoring_twice_is_idempotent(self):
        item = make_source_item(id=1, archived=True)
        repo = FakeSourceItemRepository([item])
        use_case = RestoreSourceItem(repo, uow=FakeUnitOfWork())
        await use_case.execute(actor=self.actor, item_id=1)
        result = await use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is False

    async def test_restore_conflicts_when_spec_already_taken_by_a_live_item(self):
        archived = make_source_item(id=1, type_id=1, archived=True)
        live = make_source_item(id=2, type_id=1, archived=False)
        repo = FakeSourceItemRepository([archived, live])
        with pytest.raises(SourceItemDuplicateSpecError):
            await RestoreSourceItem(repo, uow=FakeUnitOfWork()).execute(actor=self.actor, item_id=1)

    async def test_not_found_raises(self):
        repo = FakeSourceItemRepository([])
        with pytest.raises(SourceItemNotFoundError):
            await RestoreSourceItem(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, item_id=999
            )

    async def test_unprivileged_cannot_restore(self):
        item = make_source_item(id=1, archived=True)
        repo = FakeSourceItemRepository([item])
        actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEMS])
        with pytest.raises(InsufficientPermissionsError):
            await RestoreSourceItem(repo, uow=FakeUnitOfWork()).execute(actor=actor, item_id=1)


# ── GetSourceItem / GetSourceItems ────────────────────────────────────────


class TestGetSourceItem:
    def setup_method(self):
        self.item = make_source_item(id=1)
        self.source_item_repo = FakeSourceItemRepository([self.item])

    async def test_gets_by_id(self):
        result = await GetSourceItem(self.source_item_repo).execute(item_id=1)
        assert result.id == 1

    async def test_not_found_raises(self):
        with pytest.raises(SourceItemNotFoundError):
            await GetSourceItem(self.source_item_repo).execute(item_id=999)

    async def test_lists_items(self):
        result = await GetSourceItems(self.source_item_repo).execute(SourceItemFilterDto())
        assert result.total == 1
        assert result.items[0].id == 1

    async def test_archived_excluded_by_default(self):
        await self.source_item_repo.save(make_source_item(id=2, archived=True))
        result = await GetSourceItems(self.source_item_repo).execute(SourceItemFilterDto())
        assert result.total == 1

    async def test_include_archived_returns_everything(self):
        await self.source_item_repo.save(make_source_item(id=2, archived=True))
        result = await GetSourceItems(self.source_item_repo).execute(
            SourceItemFilterDto(include_archived=True)
        )
        assert result.total == 2

    def test_inactive_item_active_check(self):
        inactive = make_source_item(id=2, status=SourceItemCatalogueStatus.INACTIVE)
        from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules

        with pytest.raises(SourceItemInactiveError):
            SourceItemCatalogueRules.assert_item_active(inactive)
