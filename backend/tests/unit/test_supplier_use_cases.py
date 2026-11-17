"""
Unit tests for all supplier use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.supplier_dto import CreateSupplierCommand
from src.modules.catalogue.application.dto.supplier_dto import UpdateSupplierCommand
from src.modules.catalogue.application.use_cases.supplier.archive_supplier import ArchiveSupplier
from src.modules.catalogue.application.use_cases.supplier.create_supplier import CreateSupplier
from src.modules.catalogue.application.use_cases.supplier.get_supplier import GetSupplier
from src.modules.catalogue.application.use_cases.supplier.get_supplier import GetSuppliers
from src.modules.catalogue.application.use_cases.supplier.restore_supplier import RestoreSupplier
from src.modules.catalogue.application.use_cases.supplier.update_supplier import UpdateSupplier
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.errors import SupplierAlreadyExistsError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_supplier(
    id: int = 1,
    name: str = "Acme Corp",
    vat_id: str | None = None,
    archived: bool = False,
) -> Supplier:
    return Supplier(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        name=name,
        legal_name=None,
        vat_id=vat_id,
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


class FakeSupplierRepository:
    def __init__(self, suppliers: list[Supplier] | None = None):
        self._suppliers: dict[int, Supplier] = {}
        self._next_id = 1
        for s in suppliers or []:
            self._suppliers[s.id] = s
            self._next_id = max(self._next_id, s.id + 1)

    async def get_by_id(self, id: int) -> Supplier | None:
        return self._suppliers.get(id)

    async def lock_for_update(self, id: int) -> None:
        return None

    async def get_by_vat_id(self, vat_id: str) -> Supplier | None:
        return next(
            (s for s in self._suppliers.values() if s.vat_id == vat_id and not s.archived), None
        )

    async def get_multi(self, filters: SupplierFilterDto) -> tuple[int, list[Supplier]]:
        results = list(self._suppliers.values())
        if filters.name:
            results = [s for s in results if filters.name.lower() in s.name.lower()]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def save(self, supplier: Supplier) -> Supplier:
        if supplier.id == 0:
            supplier.id = self._next_id
            self._next_id += 1
        self._suppliers[supplier.id] = supplier
        return supplier

    async def delete(self, supplier: Supplier) -> None:
        raise NotImplementedError


# ── CreateSupplier ────────────────────────────────────────────────────


class TestCreateSupplier:
    def setup_method(self):
        self.repo = FakeSupplierRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SUPPLIERS])
        self.use_case = CreateSupplier(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> CreateSupplierCommand:
        defaults = dict(name="New Supplier")
        defaults.update(kwargs)
        return CreateSupplierCommand(**defaults)

    async def test_creates_supplier_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == "New Supplier"
        assert result.id > 0

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_duplicate_vat_id_raises(self):
        await self.repo.save(make_supplier(vat_id="AT12345"))
        with pytest.raises(SupplierAlreadyExistsError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(vat_id="AT12345"))

    async def test_no_vat_id_skips_uniqueness_check(self):
        await self.repo.save(make_supplier(vat_id=None))
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(vat_id=None))
        assert result.id > 0

    async def test_level_defaults_to_B(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.level == "B"

    async def test_creator_id_is_set_from_actor(self):
        actor = make_user(id=42, permissions=[Permission.WRITE_SUPPLIERS])
        result = await self.use_case.execute(actor=actor, cmd=self._cmd())
        assert result.creator_id == 42


# ── UpdateSupplier ────────────────────────────────────────────────────


class TestUpdateSupplier:
    def setup_method(self):
        self.supplier = make_supplier(id=1, name="Old Name", vat_id="VAT-001")
        self.repo = FakeSupplierRepository([self.supplier])
        self.actor = make_user(permissions=[Permission.WRITE_SUPPLIERS])
        self.use_case = UpdateSupplier(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> UpdateSupplierCommand:
        defaults = dict(name="Updated Supplier", vat_id="VAT-001")
        defaults.update(kwargs)
        return UpdateSupplierCommand(**defaults)

    async def test_updates_supplier_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, supplier_id=1, cmd=self._cmd(name="New Name")
        )
        assert result.name == "New Name"

    async def test_not_found_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(actor=self.actor, supplier_id=999, cmd=self._cmd())

    async def test_unprivileged_user_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, supplier_id=1, cmd=self._cmd())

    async def test_changing_to_existing_vat_id_raises(self):
        await self.repo.save(make_supplier(id=2, name="Other", vat_id="VAT-002"))
        with pytest.raises(SupplierAlreadyExistsError):
            await self.use_case.execute(
                actor=self.actor, supplier_id=1, cmd=self._cmd(vat_id="VAT-002")
            )

    async def test_keeping_same_vat_id_does_not_raise(self):
        result = await self.use_case.execute(
            actor=self.actor, supplier_id=1, cmd=self._cmd(vat_id="VAT-001")
        )
        assert result.vat_id == "VAT-001"


# ── ArchiveSupplier / RestoreSupplier ───────────────────────────────────


class TestArchiveSupplier:
    def setup_method(self):
        self.supplier = make_supplier(id=1)
        self.repo = FakeSupplierRepository([self.supplier])
        self.actor = make_user(permissions=[Permission.DELETE_SUPPLIERS])
        self.use_case = ArchiveSupplier(self.repo, uow=FakeUnitOfWork())

    async def test_archives_supplier_successfully(self):
        result = await self.use_case.execute(actor=self.actor, supplier_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, supplier_id=1)
        result = await self.use_case.execute(actor=self.actor, supplier_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(actor=self.actor, supplier_id=999)

    async def test_unprivileged_user_cannot_archive(self):
        actor = make_user(permissions=[Permission.WRITE_SUPPLIERS])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, supplier_id=1)


class TestRestoreSupplier:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.DELETE_SUPPLIERS])

    async def test_restores_supplier_successfully(self):
        supplier = make_supplier(id=1, archived=True)
        repo = FakeSupplierRepository([supplier])
        result = await RestoreSupplier(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, supplier_id=1
        )
        assert result.archived is False

    async def test_restoring_twice_is_idempotent(self):
        supplier = make_supplier(id=1, archived=True)
        repo = FakeSupplierRepository([supplier])
        use_case = RestoreSupplier(repo, uow=FakeUnitOfWork())
        await use_case.execute(actor=self.actor, supplier_id=1)
        result = await use_case.execute(actor=self.actor, supplier_id=1)
        assert result.archived is False

    async def test_restore_conflicts_when_vat_id_already_taken_by_a_live_supplier(self):
        archived = make_supplier(id=1, name="Old Acme", vat_id="ATU1", archived=True)
        live = make_supplier(id=2, name="New Acme", vat_id="ATU1", archived=False)
        repo = FakeSupplierRepository([archived, live])
        with pytest.raises(SupplierAlreadyExistsError):
            await RestoreSupplier(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, supplier_id=1
            )

    async def test_not_found_raises(self):
        repo = FakeSupplierRepository([])
        with pytest.raises(SupplierNotFoundError):
            await RestoreSupplier(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, supplier_id=999
            )

    async def test_unprivileged_user_cannot_restore(self):
        supplier = make_supplier(id=1, archived=True)
        repo = FakeSupplierRepository([supplier])
        actor = make_user(permissions=[Permission.WRITE_SUPPLIERS])
        with pytest.raises(InsufficientPermissionsError):
            await RestoreSupplier(repo, uow=FakeUnitOfWork()).execute(actor=actor, supplier_id=1)


# ── GetSupplier / GetSuppliers ────────────────────────────────────────


class TestGetSupplier:
    def setup_method(self):
        self.suppliers = [
            make_supplier(id=1, name="Alpha"),
            make_supplier(id=2, name="Beta"),
            make_supplier(id=3, name="Gamma"),
        ]
        self.repo = FakeSupplierRepository(self.suppliers)

    async def test_get_existing_supplier(self):
        result = await GetSupplier(self.repo).execute(supplier_id=1)
        assert result.name == "Alpha"

    async def test_get_nonexistent_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await GetSupplier(self.repo).execute(supplier_id=999)

    async def test_get_all(self):
        result = await GetSuppliers(self.repo).execute(filters=SupplierFilterDto())
        assert result.total == 3
        assert len(result.items) == 3

    async def test_get_with_limit(self):
        result = await GetSuppliers(self.repo).execute(filters=SupplierFilterDto(limit=2))
        assert len(result.items) == 2

    async def test_get_with_name_filter(self):
        result = await GetSuppliers(self.repo).execute(filters=SupplierFilterDto(name="alpha"))
        assert result.total == 1
        assert result.items[0].name == "Alpha"
