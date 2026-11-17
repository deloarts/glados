"""
Behavioural tests proving that a use case checks the actor's permission
before it loads the entity by id. Without this order, an unprivileged
actor gets a different exception for a missing id (not found) than for
an existing one (insufficient permissions), which lets an unauthorized
caller learn whether an id exists at all. Each fake repository below
raises if any method other than the lookup used for the ordering check
is called, so a test only passes if the permission check truly runs
first and short-circuits before any further repository access.

Five of the six use cases below were reordered to close this gap. The
sixth, DeleteDemandItem, is a documented exception: its permission rule
has no baseline requirement at all, a demand's creator may cancel it
with no special permission, and only overriding someone else's demand
needs manage:demand_items, so authorization is inseparable from the
fetched entity and the gap cannot be closed without changing that rule.
"""

import pytest

from src.modules.catalogue.application.dto.customer_dto import UpdateCustomerCommand
from src.modules.catalogue.application.dto.supplier_dto import UpdateSupplierCommand
from src.modules.catalogue.application.use_cases.customer.update_customer import UpdateCustomer
from src.modules.catalogue.application.use_cases.made_item.archive_made_item import ArchiveMadeItem
from src.modules.catalogue.application.use_cases.supplier.update_supplier import UpdateSupplier
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.fulfillment.application.dto.bought_item_demand_bucket_dto import (
    UpdateBoughtItemDemandBucketCommand,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.delete_demand_item import (
    DeleteDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand_bucket.update_bucket import (
    UpdateBucket,
)
from src.modules.fulfillment.application.use_cases.machine_pool.archive_pool import (
    ArchiveMachinePool,
)
from src.modules.fulfillment.domain.errors import BoughtItemDemandBucketNotFoundError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Shared helper ────────────────────────────────────────────────────────


class _EmptyRepository:
    """A repository with nothing in it: `get_by_id` always returns None,
    and any other method raises, so a test only passes if the permission
    check runs (and raises) before the use case ever reaches a fetch or
    a mutation."""

    async def get_by_id(self, id: int) -> None:
        return None

    async def lock_for_update(self, id: int) -> None:
        """An edit locks the row before it reads it, after its permission
        check, and the lock reads nothing."""

    def __getattr__(self, name: str):
        def _unexpected(*args, **kwargs):
            raise AssertionError(
                f"{name}() should not have been called: the permission check "
                "must raise before any further repository access."
            )

        return _unexpected


# ── UpdateSupplier ───────────────────────────────────────────────────────


class TestSupplierUpdatePermissionBeforeFetch:
    async def test_unprivileged_actor_and_missing_id_raises_permission_error(self):
        use_case = UpdateSupplier(_EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[])
        cmd = UpdateSupplierCommand(name="Updated Supplier", vat_id="VAT-001")

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, supplier_id=999, cmd=cmd)

    async def test_missing_id_alone_would_have_raised_not_found(self):
        """Sanity check: the repository genuinely has nothing at id 999,
        so a privileged actor still gets the not-found error, proving the
        permission error above is not a fluke of the fake repository."""
        use_case = UpdateSupplier(_EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[Permission.WRITE_SUPPLIERS])
        cmd = UpdateSupplierCommand(name="Updated Supplier", vat_id="VAT-001")

        with pytest.raises(SupplierNotFoundError):
            await use_case.execute(actor=actor, supplier_id=999, cmd=cmd)


# ── UpdateCustomer ───────────────────────────────────────────────────────


class TestCustomerUpdatePermissionBeforeFetch:
    async def test_unprivileged_actor_and_missing_id_raises_permission_error(self):
        use_case = UpdateCustomer(_EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[])
        cmd = UpdateCustomerCommand(name="Acme Corp", level="B")

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, customer_id=999, cmd=cmd)

    async def test_missing_id_alone_would_have_raised_not_found(self):
        use_case = UpdateCustomer(_EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[Permission.WRITE_PROJECTS])
        cmd = UpdateCustomerCommand(name="Acme Corp", level="B")

        with pytest.raises(CustomerNotFoundError):
            await use_case.execute(actor=actor, customer_id=999, cmd=cmd)


# ── ArchiveMadeItem ──────────────────────────────────────────────────────


class TestMadeItemArchivePermissionBeforeFetch:
    async def test_unprivileged_actor_and_missing_id_raises_permission_error(self):
        use_case = ArchiveMadeItem(_EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[])

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, item_id=999)

    async def test_missing_id_alone_would_have_raised_not_found(self):
        use_case = ArchiveMadeItem(_EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[Permission.DELETE_MADE_ITEMS])

        with pytest.raises(MadeItemNotFoundError):
            await use_case.execute(actor=actor, item_id=999)


# ── ArchiveMachinePool ───────────────────────────────────────────────────


class _NullEventBus:
    async def publish(self, event) -> None:
        raise AssertionError("publish() should not have been called before the fetch.")


class TestMachinePoolArchivePermissionBeforeFetch:
    async def test_unprivileged_actor_and_missing_id_raises_permission_error(self):
        use_case = ArchiveMachinePool(
            _EmptyRepository(), event_bus=_NullEventBus(), uow=FakeUnitOfWork()
        )
        actor = make_user(permissions=[])

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, pool_id=999)

    async def test_missing_id_alone_would_have_raised_not_found(self):
        use_case = ArchiveMachinePool(
            _EmptyRepository(), event_bus=_NullEventBus(), uow=FakeUnitOfWork()
        )
        actor = make_user(permissions=[Permission.WRITE_MACHINES])

        with pytest.raises(MachinePoolNotFoundError):
            await use_case.execute(actor=actor, pool_id=999)


# ── UpdateBucket (bought item demand bucket) ──────────────────────────────


class TestBoughtItemDemandBucketUpdatePermissionBeforeFetch:
    async def test_unprivileged_actor_and_missing_id_raises_permission_error(self):
        use_case = UpdateBucket(_EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[])
        cmd = UpdateBoughtItemDemandBucketCommand(name="Urgent", color="#00ff00")

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, bucket_id=999, cmd=cmd)

    async def test_missing_id_alone_would_have_raised_not_found(self):
        use_case = UpdateBucket(_EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        cmd = UpdateBoughtItemDemandBucketCommand(name="Urgent", color="#00ff00")

        with pytest.raises(BoughtItemDemandBucketNotFoundError):
            await use_case.execute(actor=actor, bucket_id=999, cmd=cmd)


# ── DeleteDemandItem (bought item demand): documented gap ────────────────


class TestBoughtItemDemandDeleteStillOracle:
    """DeleteDemandItem is intentionally left unreordered, see this
    module's docstring. This test documents the residual gap rather than
    a fix: even a fully unprivileged actor still gets not-found, not a
    permission error, for a missing id, because assert_can_cancel_demand
    has no permission requirement it could check before the demand is
    loaded."""

    async def test_unprivileged_actor_and_missing_id_still_raises_not_found(self):
        use_case = DeleteDemandItem(_EmptyRepository(), _EmptyRepository(), uow=FakeUnitOfWork())
        actor = make_user(permissions=[])

        with pytest.raises(DemandItemNotFoundError):
            await use_case.execute(actor=actor, demand_id=999)
