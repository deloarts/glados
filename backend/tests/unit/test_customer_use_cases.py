"""
Unit tests for all customer use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.application.dto.customer_dto import CreateCustomerCommand
from src.modules.catalogue.application.dto.customer_dto import UpdateCustomerCommand
from src.modules.catalogue.application.use_cases.customer.archive_customer import ArchiveCustomer
from src.modules.catalogue.application.use_cases.customer.create_customer import CreateCustomer
from src.modules.catalogue.application.use_cases.customer.get_customer import GetCustomer
from src.modules.catalogue.application.use_cases.customer.get_customer import GetCustomers
from src.modules.catalogue.application.use_cases.customer.restore_customer import RestoreCustomer
from src.modules.catalogue.application.use_cases.customer.update_customer import UpdateCustomer
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.errors import CustomerAlreadyExistsError
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.catalogue.ports.outbound.repositories.customer_repository import CustomerFilterDto
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_customer(
    id: int = 1,
    name: str = "Acme Corp",
    vat_id: str | None = None,
    archived: bool = False,
) -> Customer:
    return Customer(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=archived,
        name=name,
        legal_name=None,
        vat_id=vat_id,
        level=CustomerLevel.B,
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        creator_id=1,
    )


class FakeCustomerRepository:
    def __init__(self, customers: list[Customer] | None = None):
        self._customers: dict[int, Customer] = {}
        self._next_id = 1
        for c in customers or []:
            self._customers[c.id] = c
            self._next_id = max(self._next_id, c.id + 1)

    async def get_by_id(self, id: int) -> Customer | None:
        return self._customers.get(id)

    async def lock_for_update(self, id: int) -> None:
        return None

    async def get_by_vat_id(self, vat_id: str) -> Customer | None:
        return next(
            (c for c in self._customers.values() if c.vat_id == vat_id and not c.archived), None
        )

    async def get_multi(self, filters: CustomerFilterDto) -> tuple[int, list[Customer]]:
        results = list(self._customers.values())
        if filters.name:
            results = [c for c in results if filters.name.lower() in c.name.lower()]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def save(self, customer: Customer) -> Customer:
        if customer.id == 0:
            customer.id = self._next_id
            self._next_id += 1
        self._customers[customer.id] = customer
        return customer

    async def delete(self, customer: Customer) -> None:
        raise NotImplementedError


# ── CreateCustomer ────────────────────────────────────────────────────


class TestCreateCustomer:
    def setup_method(self):
        self.repo = FakeCustomerRepository()
        self.actor = make_user(permissions=[Permission.WRITE_PROJECTS])
        self.use_case = CreateCustomer(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> CreateCustomerCommand:
        defaults = dict(name="Acme Corp")
        defaults.update(kwargs)
        return CreateCustomerCommand(**defaults)

    async def test_creates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == "Acme Corp"
        assert result.id > 0

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_duplicate_vat_id_raises(self):
        await self.repo.save(make_customer(name="Existing", vat_id="ATU12345678"))
        with pytest.raises(CustomerAlreadyExistsError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(vat_id="ATU12345678"))

    async def test_no_vat_id_does_not_trigger_duplicate_check(self):
        await self.repo.save(make_customer(name="Existing", vat_id=None))
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.id > 0

    async def test_creator_id_is_set(self):
        actor = make_user(id=7, permissions=[Permission.WRITE_PROJECTS])
        result = await self.use_case.execute(actor=actor, cmd=self._cmd())
        assert result.creator_id == 7

    async def test_default_level_is_b(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.level == "B"


# ── UpdateCustomer ────────────────────────────────────────────────────


class TestUpdateCustomer:
    def setup_method(self):
        self.customer = make_customer(id=1, name="Acme Corp")
        self.repo = FakeCustomerRepository([self.customer])
        self.actor = make_user(permissions=[Permission.WRITE_PROJECTS])
        self.use_case = UpdateCustomer(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> UpdateCustomerCommand:
        defaults = dict(name="Acme Corp", level="B")
        defaults.update(kwargs)
        return UpdateCustomerCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, customer_id=1, cmd=self._cmd(name="Acme Corp Renamed")
        )
        assert result.name == "Acme Corp Renamed"

    async def test_not_found_raises(self):
        with pytest.raises(CustomerNotFoundError):
            await self.use_case.execute(actor=self.actor, customer_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, customer_id=1, cmd=self._cmd())

    async def test_changing_to_existing_vat_id_raises(self):
        await self.repo.save(make_customer(id=2, name="Other", vat_id="ATU99999999"))
        with pytest.raises(CustomerAlreadyExistsError):
            await self.use_case.execute(
                actor=self.actor, customer_id=1, cmd=self._cmd(vat_id="ATU99999999")
            )

    async def test_keeping_same_vat_id_does_not_raise(self):
        self.customer.vat_id = "ATU12345678"
        result = await self.use_case.execute(
            actor=self.actor, customer_id=1, cmd=self._cmd(vat_id="ATU12345678")
        )
        assert result.vat_id == "ATU12345678"


# ── ArchiveCustomer / RestoreCustomer ───────────────────────────────────


class TestArchiveCustomer:
    def setup_method(self):
        self.customer = make_customer(id=1)
        self.repo = FakeCustomerRepository([self.customer])
        self.actor = make_user(permissions=[Permission.MANAGE_PROJECTS])
        self.use_case = ArchiveCustomer(self.repo, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, customer_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, customer_id=1)
        result = await self.use_case.execute(actor=self.actor, customer_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(CustomerNotFoundError):
            await self.use_case.execute(actor=self.actor, customer_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[Permission.WRITE_PROJECTS])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, customer_id=1)


class TestRestoreCustomer:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.MANAGE_PROJECTS])

    async def test_restores_successfully(self):
        customer = make_customer(id=1, archived=True)
        repo = FakeCustomerRepository([customer])
        result = await RestoreCustomer(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, customer_id=1
        )
        assert result.archived is False

    async def test_restore_conflicts_when_vat_id_already_taken_by_a_live_customer(self):
        archived = make_customer(id=1, name="Old", vat_id="ATU1", archived=True)
        live = make_customer(id=2, name="New", vat_id="ATU1", archived=False)
        repo = FakeCustomerRepository([archived, live])
        with pytest.raises(CustomerAlreadyExistsError):
            await RestoreCustomer(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, customer_id=1
            )

    async def test_not_found_raises(self):
        repo = FakeCustomerRepository([])
        with pytest.raises(CustomerNotFoundError):
            await RestoreCustomer(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, customer_id=999
            )


# ── GetCustomer / GetCustomers ────────────────────────────────────────


class TestGetCustomer:
    def setup_method(self):
        self.customers = [
            make_customer(id=1, name="Alpha"),
            make_customer(id=2, name="Beta"),
            make_customer(id=3, name="Gamma"),
        ]
        self.repo = FakeCustomerRepository(self.customers)

    async def test_get_existing(self):
        result = await GetCustomer(self.repo).execute(customer_id=1)
        assert result.name == "Alpha"

    async def test_get_nonexistent_raises(self):
        with pytest.raises(CustomerNotFoundError):
            await GetCustomer(self.repo).execute(customer_id=999)

    async def test_get_all(self):
        result = await GetCustomers(self.repo).execute(filters=CustomerFilterDto())
        assert result.total == 3
        assert len(result.items) == 3

    async def test_get_with_limit(self):
        result = await GetCustomers(self.repo).execute(filters=CustomerFilterDto(limit=1))
        assert len(result.items) == 1

    async def test_get_with_name_filter(self):
        result = await GetCustomers(self.repo).execute(filters=CustomerFilterDto(name="beta"))
        assert result.total == 1
        assert result.items[0].name == "Beta"
