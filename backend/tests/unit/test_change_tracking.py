"""
Unit tests for live row-sync change capture
(src/modules/platform/adapters/outbound/persistence/change_tracking.py). Exercises real
SQLAlchemy session events against a throwaway in-memory SQLite engine,
mocking the Session wouldn't test anything meaningful here, since the
behavior under test *is* exactly when session.new/dirty/deleted are
populated relative to the event hooks. No Redis server: the publish call
is replaced with an in-memory fake.
"""

import asyncio
import importlib
import json
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
import redis
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_file_model import (
    BoughtItemFileOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_file_model import (
    MadeItemFileOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_file_model import (
    SourceItemFileOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.machine_pool_model import (
    MachinePoolOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.services.scheduling import ExternalForecast
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderPlanningFields,
)
from src.modules.platform.adapters.outbound.persistence import change_tracking
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.change_tracking import (
    register_change_tracking,
)
from src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model import (
    AcknowledgementOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model import (
    AcknowledgementRecipientOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.banner import (
    AdminBannerSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.infrastructure.logging.context import user_id_var
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
    ProductDeviceComponentOrmModel,
)
from tests.unit.auto_plan._helpers import make_order

# Import every model module directly (rather than relying on
# alembic_imports.py) so Base.metadata is guaranteed complete for
# create_all() to resolve every FK, independent of alembic wiring.
for _module_name in model_module_names():
    importlib.import_module(_module_name)


class FakeRedis:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel, payload):
        if self.fail:
            raise redis.ConnectionError("redis is down")
        self.published.append((channel, payload))


@pytest.fixture(autouse=True)
def _reset_user_id_var():
    # user_id_var is a ContextVar with process-wide default scope in a sync
    # test run (no per-request isolation like in the app), without this,
    # test_create_signals_created's user_id_var.set(7) would leak into every
    # test that runs after it in the same session.
    token = user_id_var.set(None)
    yield
    user_id_var.reset(token)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(change_tracking, "get_async_redis_client", lambda: fake)
    return fake


@pytest.fixture
def session_factory():
    """Sync sessions of a Session subclass private to this test, so the
    listeners register_change_tracking attaches to the async factory's sync
    session class never reach any other session in the process. The commits
    still run inside the test's event loop, which is where after_commit
    schedules its publish task."""

    class _TrackedSession(Session):
        pass

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    register_change_tracking(async_sessionmaker(sync_session_class=_TrackedSession))
    return sessionmaker(bind=engine, class_=_TrackedSession)


async def _drain() -> None:
    """Waits for the publish tasks the after_commit hook handed to the loop."""
    await asyncio.gather(*change_tracking._publish_tasks)


async def _signals(fake: FakeRedis) -> list[dict]:
    """Flattens every publish() call into one list of signal dicts, in order."""
    await _drain()
    return [signal for _channel, payload in fake.published for signal in json.loads(payload)]


def _pool_signal(row_id: int, action: str, actor_id: int | None = None) -> dict:
    return {
        "resource": LiveResource.MACHINE_POOLS,
        "id": row_id,
        "action": action,
        "actor_id": actor_id,
    }


def _make_pool(session: Session, name: str = "Pool A") -> MachinePoolOrmModel:
    pool = MachinePoolOrmModel(name=name, created=date.today(), creator_id=1)
    session.add(pool)
    return pool


def _make_order(session: Session, number: str = "ORD-1") -> OrderOrmModel:
    order = OrderOrmModel(order_number=number, created=date.today(), creator_id=1, supplier_id=1)
    session.add(order)
    return order


def _make_order_item(
    session: Session,
    order: OrderOrmModel,
    *,
    line_type: str = OrderLineType.BOUGHT.value,
    bought_item_id: int | None = 1,
    lot_position_id: int | None = None,
) -> OrderItemOrmModel:
    # bought_item_id defaults to 1: ck_order_item_line_type requires a
    # BOUGHT line to actually carry a bought_item_id. This test only
    # needs *a* row to exist to exercise change-tracking, not a real
    # catalogue reference, but the constraint doesn't know that. Callers
    # building a MADE line instead (lot_position_id set) must pass
    # bought_item_id=None.
    item = OrderItemOrmModel(
        created=date.today(),
        quantity=1.0,
        unit="pcs",
        creator_id=1,
        order_id=order.id,
        supplier_id=1,
        project_id=1,
        line_type=line_type,
        bought_item_id=bought_item_id,
        lot_position_id=lot_position_id,
    )
    session.add(item)
    return item


def _make_bought_item_demand(session: Session) -> BoughtItemDemandItemOrmModel:
    demand = BoughtItemDemandItemOrmModel(
        created=date.today(),
        quantity=1.0,
        unit="pcs",
        creator_id=1,
        item_id=1,
        project_id=1,
    )
    session.add(demand)
    return demand


def _make_bought_item_allocation(
    session: Session, demand: BoughtItemDemandItemOrmModel, quantity: float = 1.0
) -> BoughtItemAllocationOrmModel:
    allocation = BoughtItemAllocationOrmModel(demand_item_id=demand.id, quantity=quantity)
    session.add(allocation)
    return allocation


def _make_lot(session: Session, number: str = "LOT-1") -> ProductionLotOrmModel:
    lot = ProductionLotOrmModel(
        lot_number=number,
        quantity=1.0,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        created=date.today(),
    )
    session.add(lot)
    return lot


def _make_lot_position(
    session: Session, lot: ProductionLotOrmModel, sequence: int = 1
) -> LotPositionOrmModel:
    position = LotPositionOrmModel(
        created=date.today(), sequence=sequence, quantity=1.0, creator_id=1, lot_id=lot.id
    )
    session.add(position)
    return position


def _make_production_order(
    session: Session, position: LotPositionOrmModel, number: str = "PO-1"
) -> ProductionOrderOrmModel:
    production_order = ProductionOrderOrmModel(
        created=date.today(),
        production_order_number=number,
        quantity=1.0,
        creator_id=1,
        lot_position_id=position.id,
    )
    session.add(production_order)
    return production_order


def _make_source_item_demand(
    session: Session, lot: ProductionLotOrmModel
) -> SourceItemDemandItemOrmModel:
    demand = SourceItemDemandItemOrmModel(
        created=date.today(),
        quantity=1.0,
        unit="pcs",
        creator_id=1,
        lot_id=lot.id,
        project_id=1,
    )
    session.add(demand)
    return demand


# ── Basic actions ─────────────────────────────────────────────────────


async def test_create_signals_created(session_factory, fake_redis):
    with session_factory() as session:
        user_id_var.set(7)
        pool = _make_pool(session)
        session.commit()
        pool_id = pool.id

    assert await _signals(fake_redis) == [_pool_signal(pool_id, "created", actor_id=7)]


async def test_update_signals_updated(session_factory, fake_redis):
    with session_factory() as session:
        pool = _make_pool(session)
        session.commit()
        pool_id = pool.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        pool = session.get(MachinePoolOrmModel, pool_id)
        pool.name = "Renamed"
        session.commit()

    assert await _signals(fake_redis) == [_pool_signal(pool_id, "updated")]


async def test_noop_update_produces_no_signal(session_factory, fake_redis):
    """Setting a column to its current value marks the row dirty but not
    actually modified, the is_modified guard must filter this out, or
    every incidental re-save would spam every viewer with a fake change."""
    with session_factory() as session:
        pool = _make_pool(session)
        session.commit()
        pool_id = pool.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        pool = session.get(MachinePoolOrmModel, pool_id)
        pool.name = pool.name
        session.commit()

    assert await _signals(fake_redis) == []


async def test_hard_delete_signals_deleted(session_factory, fake_redis):
    with session_factory() as session:
        pool = _make_pool(session)
        session.commit()
        pool_id = pool.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        pool = session.get(MachinePoolOrmModel, pool_id)
        session.delete(pool)
        session.commit()

    assert await _signals(fake_redis) == [_pool_signal(pool_id, "deleted")]


async def test_soft_delete_signals_updated_not_deleted(session_factory, fake_redis):
    """MachinePoolOrmModel.archived is a soft-delete (archive) flag
    (repository sets it and saves rather than issuing DELETE), so the ORM
    sees this as a dirty row, not a session.deleted one. The row therefore
    disappears from list queries but the signal says "updated", the
    client's existing "id missing from the ids-refetch response" fallback
    is what actually drops it from the table, not the action label."""
    with session_factory() as session:
        pool = _make_pool(session)
        session.commit()
        pool_id = pool.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        pool = session.get(MachinePoolOrmModel, pool_id)
        pool.archived = True
        session.commit()

    assert await _signals(fake_redis) == [_pool_signal(pool_id, "updated")]


# ── Scope and mapping ────────────────────────────────────────────────


async def test_unmapped_model_produces_no_signal(session_factory, fake_redis):
    with session_factory() as session:
        session.add(CustomerOrmModel(name="Acme", created=date.today(), creator_id=1))
        session.commit()

    assert await _signals(fake_redis) == []


async def test_bought_item_file_signals_its_item_as_updated(session_factory, fake_redis):
    # SQLite leaves foreign keys unchecked here, so the file needs no item row.
    with session_factory() as session:
        session.add(
            BoughtItemFileOrmModel(
                bought_item_id=42,
                file_name="picture.png",
                stored_name="stored-picture.png",
                mime_type="image/png",
                size_bytes=1,
                storage_path="bought/42/stored-picture.png",
                sha256="0" * 64,
                category="thumbnail",
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        session.commit()

    assert await _signals(fake_redis) == [
        {"resource": LiveResource.BOUGHT_ITEMS, "id": 42, "action": "updated", "actor_id": None}
    ]


def _make_catalogue_item(session: Session, resource: str) -> Base:
    now = datetime.now(UTC)
    common = {"created": now, "changed": now, "changes": [], "creator_id": 1}
    item: Base
    if resource == LiveResource.BOUGHT_ITEMS:
        item = BoughtItemOrmModel(
            **common,
            order_code_1="OC-1",
            status="active",
            article_name="Screw",
            data_source="WEB",
            manufacturer_id=1,
        )
    elif resource == LiveResource.MADE_ITEMS:
        item = MadeItemOrmModel(
            **common, revision="A", article_name="Bracket", status="active", data_source="CAD"
        )
    else:
        item = SourceItemOrmModel(**common, type_id=1, material="S235", status="active")
    session.add(item)
    session.flush()
    return item


def _catalogue_signal(resource: str, row_id: int, action: str) -> dict:
    return {"resource": resource, "id": row_id, "action": action, "actor_id": None}


_CATALOGUE_RESOURCES = [
    LiveResource.BOUGHT_ITEMS,
    LiveResource.MADE_ITEMS,
    LiveResource.SOURCE_ITEMS,
]


@pytest.mark.parametrize("resource", _CATALOGUE_RESOURCES)
async def test_catalogue_item_create_signals_created(session_factory, fake_redis, resource):
    with session_factory() as session:
        item = _make_catalogue_item(session, resource)
        session.commit()
        item_id = item.id

    assert await _signals(fake_redis) == [_catalogue_signal(resource, item_id, "created")]


@pytest.mark.parametrize("resource", _CATALOGUE_RESOURCES)
async def test_catalogue_item_update_signals_updated(session_factory, fake_redis, resource):
    with session_factory() as session:
        item = _make_catalogue_item(session, resource)
        session.commit()
        item_id = item.id
        model = type(item)

    await _drain()
    fake_redis.published.clear()

    with session_factory() as session:
        session.get(model, item_id).note = "Changed elsewhere"
        session.commit()

    assert await _signals(fake_redis) == [_catalogue_signal(resource, item_id, "updated")]


@pytest.mark.parametrize("resource", _CATALOGUE_RESOURCES)
async def test_catalogue_item_archive_signals_updated(session_factory, fake_redis, resource):
    """Archiving is a soft delete, so the row is dirty rather than deleted;
    the table drops it when the id refetch no longer returns it."""
    with session_factory() as session:
        item = _make_catalogue_item(session, resource)
        session.commit()
        item_id = item.id
        model = type(item)

    await _drain()
    fake_redis.published.clear()

    with session_factory() as session:
        session.get(model, item_id).archived = True
        session.commit()

    assert await _signals(fake_redis) == [_catalogue_signal(resource, item_id, "updated")]


@pytest.mark.parametrize(
    ("model", "fk", "category", "resource"),
    [
        (MadeItemFileOrmModel, "made_item_id", "mesh", LiveResource.MADE_ITEMS),
        (SourceItemFileOrmModel, "source_item_id", "mesh", LiveResource.SOURCE_ITEMS),
    ],
)
async def test_item_file_signals_its_item_as_updated(
    session_factory, fake_redis, model, fk, category, resource
):
    # SQLite leaves foreign keys unchecked here, so the file needs no item row.
    with session_factory() as session:
        session.add(
            model(
                **{fk: 42},
                file_name="part.stl",
                stored_name="stored-part.stl",
                mime_type="model/stl",
                size_bytes=1,
                storage_path="items/42/stored-part.stl",
                sha256="0" * 64,
                category=category,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )
        )
        session.commit()

    assert await _signals(fake_redis) == [_catalogue_signal(resource, 42, "updated")]


async def test_product_device_component_signals_its_product_as_updated(session_factory, fake_redis):
    # SQLite leaves foreign keys unchecked here, so the component needs no
    # device or product row.
    with session_factory() as session:
        session.add(
            ProductDeviceComponentOrmModel(
                device_id=5, product_id=7, role_id=1, sort_order=0, signals=[]
            )
        )
        session.commit()

    assert await _signals(fake_redis) == [
        {"resource": LiveResource.PRODUCT_DEVICES, "id": 7, "action": "updated", "actor_id": None}
    ]


async def test_allocation_signals_demand_id_not_deleted_on_removal(session_factory, fake_redis):
    """Allocating/deallocating a demand signals the demand
    (BoughtItemAllocationOrmModel is in MODEL_TOPICS), so the demand table
    picks up the change without a manual refresh. Also guards the same
    child-row rule as order items: removing an
    allocation must read as the demand being updated, never deleted."""
    with session_factory() as session:
        demand = _make_bought_item_demand(session)
        session.commit()
        demand_id = demand.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        demand = session.get(BoughtItemDemandItemOrmModel, demand_id)
        allocation = _make_bought_item_allocation(session, demand)
        session.commit()
        allocation_id = allocation.id

    assert await _signals(fake_redis) == [
        {
            "resource": LiveResource.BOUGHT_ITEM_DEMANDS,
            "id": demand_id,
            "action": "updated",
            "actor_id": None,
        }
    ]

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        allocation = session.get(BoughtItemAllocationOrmModel, allocation_id)
        session.delete(allocation)
        session.commit()

    assert await _signals(fake_redis) == [
        {
            "resource": LiveResource.BOUGHT_ITEM_DEMANDS,
            "id": demand_id,
            "action": "updated",
            "actor_id": None,
        }
    ]


async def test_production_order_signals_both_its_own_topic_and_its_lot(session_factory, fake_redis):
    """A production order's planned/actual dates are rendered inline in the
    lots table, so ProductionOrderOrmModel signals "production-lots" as well
    as "production-orders": a lots-table viewer subscribed only to
    "production-lots" sees an edited step date without a manual refresh."""
    with session_factory() as session:
        lot = _make_lot(session)
        session.flush()
        position = _make_lot_position(session, lot)
        session.flush()
        production_order = _make_production_order(session, position)
        session.commit()
        lot_id, production_order_id = lot.id, production_order.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        production_order = session.get(ProductionOrderOrmModel, production_order_id)
        production_order.planned_start = None  # touch a scheduling field
        production_order.note = "rescheduled"
        session.commit()

    assert await _signals(fake_redis) == [
        {
            "resource": LiveResource.PRODUCTION_ORDERS,
            "id": production_order_id,
            "action": "updated",
            "actor_id": None,
        },
        {
            "resource": LiveResource.PRODUCTION_LOTS,
            "id": lot_id,
            "action": "updated",
            "actor_id": None,
        },
    ]


async def test_externally_sourced_order_item_signals_its_lot_too(session_factory, fake_redis):
    """Same rule as above, for the other half of a lot's schedule: an
    externally-sourced position's order item (expected_delivery_date etc.)
    is also rendered inline in the lots table."""
    with session_factory() as session:
        lot = _make_lot(session)
        session.flush()
        position = _make_lot_position(session, lot)
        order = _make_order(session)
        session.flush()
        item = _make_order_item(
            session,
            order,
            line_type=OrderLineType.MADE.value,
            bought_item_id=None,
            lot_position_id=position.id,
        )
        session.commit()
        lot_id, order_id, item_id = lot.id, order.id, item.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        item = session.get(OrderItemOrmModel, item_id)
        item.expected_delivery_date = date.today()
        session.commit()

    assert await _signals(fake_redis) == [
        {"resource": LiveResource.ORDERS, "id": order_id, "action": "updated", "actor_id": None},
        {
            "resource": LiveResource.PRODUCTION_LOTS,
            "id": lot_id,
            "action": "updated",
            "actor_id": None,
        },
    ]


async def test_source_item_demand_signals_its_lot_too(session_factory, fake_redis):
    """A source item demand's status (open/allocated/ordered/
    delivered/fulfilled/canceled) is rendered inline in the lots table
    (LotSummaryResponse.demand_status), so SourceItemDemandItemOrmModel
    signals "production-lots" as well as "source-item-demands": allocating,
    ordering or canceling a demand reaches a lots-table viewer subscribed
    only to "production-lots" without a manual refresh."""
    with session_factory() as session:
        lot = _make_lot(session)
        session.flush()
        demand = _make_source_item_demand(session, lot)
        session.commit()
        lot_id, demand_id = lot.id, demand.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        demand = session.get(SourceItemDemandItemOrmModel, demand_id)
        demand.status = "allocated"
        session.commit()

    assert await _signals(fake_redis) == [
        {
            "resource": LiveResource.SOURCE_ITEM_DEMANDS,
            "id": demand_id,
            "action": "updated",
            "actor_id": None,
        },
        {
            "resource": LiveResource.PRODUCTION_LOTS,
            "id": lot_id,
            "action": "updated",
            "actor_id": None,
        },
    ]


async def test_ordinary_order_item_does_not_signal_production_lots(session_factory, fake_redis):
    """The production-lots topic on OrderItemOrmModel must resolve to
    nothing for the common case (lot_position_id is None); not every
    order item belongs to a lot."""
    with session_factory() as session:
        order = _make_order(session)
        session.flush()
        item = _make_order_item(session, order)
        session.commit()
        order_id, item_id = order.id, item.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        item = session.get(OrderItemOrmModel, item_id)
        item.expected_delivery_date = date.today()
        session.commit()

    assert await _signals(fake_redis) == [
        {"resource": LiveResource.ORDERS, "id": order_id, "action": "updated", "actor_id": None}
    ]


async def test_child_row_signals_parent_id(session_factory, fake_redis):
    with session_factory() as session:
        order = _make_order(session)
        session.commit()
        order_id = order.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        order = session.get(OrderOrmModel, order_id)
        _make_order_item(session, order)
        session.commit()

    # A new item on an *existing* order is never read by the client as the
    # order itself appearing: the order was already there, only its items
    # changed, so the forced action is "updated", not "created".
    assert await _signals(fake_redis) == [
        {"resource": LiveResource.ORDERS, "id": order_id, "action": "updated", "actor_id": None}
    ]


async def test_child_row_deletion_signals_updated_not_deleted(session_factory, fake_redis):
    """Deleting one order item must never read as "the order was deleted";
    that would splice the still-existing order out of every viewer's table."""
    with session_factory() as session:
        order = _make_order(session)
        session.flush()  # assigns order.id before the item needs it as an FK
        item = _make_order_item(session, order)
        session.commit()
        order_id, item_id = order.id, item.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        item = session.get(OrderItemOrmModel, item_id)
        session.delete(item)
        session.commit()

    assert await _signals(fake_redis) == [
        {"resource": LiveResource.ORDERS, "id": order_id, "action": "updated", "actor_id": None}
    ]


async def test_parent_and_child_created_together_dedupe_to_created(session_factory, fake_redis):
    """The order's own real "created" action must win over the forced
    "updated" from its new item: a client that has never seen this order
    needs the created-triggered full refresh, not a by-id patch of a row it
    doesn't have yet."""
    with session_factory() as session:
        order = _make_order(session)
        session.flush()  # assigns order.id without ending the transaction
        _make_order_item(session, order)
        session.commit()
        order_id = order.id

    assert await _signals(fake_redis) == [
        {"resource": LiveResource.ORDERS, "id": order_id, "action": "created", "actor_id": None}
    ]


async def test_parent_deleted_wins_over_child_touch_in_same_transaction(
    session_factory, fake_redis
):
    with session_factory() as session:
        order = _make_order(session)
        session.flush()  # assigns order.id before the item needs it as an FK
        item = _make_order_item(session, order)
        session.commit()
        order_id, item_id = order.id, item.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        order = session.get(OrderOrmModel, order_id)
        item = session.get(OrderItemOrmModel, item_id)
        session.delete(item)
        session.delete(order)
        session.commit()

    assert await _signals(fake_redis) == [
        {"resource": LiveResource.ORDERS, "id": order_id, "action": "deleted", "actor_id": None}
    ]


# ── Transaction semantics ────────────────────────────────────────────


async def test_rollback_discards_buffer(session_factory, fake_redis):
    with session_factory() as session:
        _make_pool(session)
        session.rollback()

    await _drain()
    assert fake_redis.published == []


async def test_multiple_flushes_before_commit_accumulate(session_factory, fake_redis):
    with session_factory() as session:
        first = _make_pool(session, name="Pool A")
        session.flush()
        second = _make_pool(session, name="Pool B")
        session.commit()
        first_id, second_id = first.id, second.id

    ids = {s["id"] for s in await _signals(fake_redis)}
    assert ids == {first_id, second_id}


# ── Bulk collapsing ───────────────────────────────────────────────────


async def test_bulk_threshold_collapses_to_one_signal(session_factory, fake_redis):
    with session_factory() as session:
        for i in range(change_tracking._BULK_THRESHOLD + 1):
            _make_pool(session, name=f"Pool {i}")
        session.commit()

    assert await _signals(fake_redis) == [_pool_signal(0, "bulk")]


async def test_below_bulk_threshold_lists_ids_individually(session_factory, fake_redis):
    with session_factory() as session:
        for i in range(change_tracking._BULK_THRESHOLD):
            _make_pool(session, name=f"Pool {i}")
        session.commit()

    signals = await _signals(fake_redis)
    assert len(signals) == change_tracking._BULK_THRESHOLD
    assert all(s["action"] == "created" for s in signals)


# ── Publish failure ───────────────────────────────────────────────────


async def test_redis_failure_does_not_raise(session_factory, monkeypatch):
    fake = FakeRedis(fail=True)
    monkeypatch.setattr(change_tracking, "get_async_redis_client", lambda: fake)

    with session_factory() as session:
        pool = _make_pool(session)
        session.commit()  # must not raise despite the publish failure

        # The row is written all the same.
        assert pool.id is not None
    await _drain()  # nor may the publish task itself


# ── Announcements (banner + acknowledgements) ────────────────────────


def _announcements_signal(row_id: int, action: str, actor_id: int | None = None) -> dict:
    return {
        "resource": LiveResource.ANNOUNCEMENTS,
        "id": row_id,
        "action": action,
        "actor_id": actor_id,
    }


def _make_banner(session: Session) -> AdminBannerSettingsOrmModel:
    banner = AdminBannerSettingsOrmModel(
        id=1, enabled=False, text="", severity="info", updated_at=datetime.now(UTC)
    )
    session.add(banner)
    return banner


def _make_ack(session: Session, text: str = "Please confirm") -> AcknowledgementOrmModel:
    ack = AcknowledgementOrmModel(
        text=text,
        severity="info",
        enabled=True,
        show_when="immediately",
        created_at=datetime.now(UTC),
        created_by_id=1,
    )
    session.add(ack)
    return ack


def _make_recipient(
    session: Session, ack: AcknowledgementOrmModel, user_id: int = 1
) -> AcknowledgementRecipientOrmModel:
    recipient = AcknowledgementRecipientOrmModel(acknowledgement_id=ack.id, user_id=user_id)
    session.add(recipient)
    return recipient


async def test_banner_settings_create_signals_announcements(session_factory, fake_redis):
    with session_factory() as session:
        _make_banner(session)
        session.commit()

    assert await _signals(fake_redis) == [_announcements_signal(1, "created")]


async def test_banner_settings_update_signals_announcements(session_factory, fake_redis):
    with session_factory() as session:
        _make_banner(session)
        session.commit()

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        banner = session.get(AdminBannerSettingsOrmModel, 1)
        banner.enabled = True
        banner.text = "We upgrade at 18:00"
        session.commit()

    assert await _signals(fake_redis) == [_announcements_signal(1, "updated")]


async def test_acknowledgement_create_signals_announcements(session_factory, fake_redis):
    with session_factory() as session:
        ack = _make_ack(session)
        session.commit()
        ack_id = ack.id

    assert await _signals(fake_redis) == [_announcements_signal(ack_id, "created")]


async def test_acknowledgement_enabled_toggle_signals_announcements(session_factory, fake_redis):
    with session_factory() as session:
        ack = _make_ack(session)
        session.commit()
        ack_id = ack.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        ack = session.get(AcknowledgementOrmModel, ack_id)
        ack.enabled = False
        session.commit()

    assert await _signals(fake_redis) == [_announcements_signal(ack_id, "updated")]


async def test_acknowledgement_delete_signals_announcements(session_factory, fake_redis):
    with session_factory() as session:
        ack = _make_ack(session)
        session.commit()
        ack_id = ack.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        ack = session.get(AcknowledgementOrmModel, ack_id)
        session.delete(ack)
        session.commit()

    assert await _signals(fake_redis) == [_announcements_signal(ack_id, "deleted")]


async def test_acknowledgement_recipient_create_signals_its_acknowledgement_as_updated(
    session_factory, fake_redis
):
    """Contract proof: a composite-PK row (acknowledgement_id,
    user_id, no own int id) still resolves through _resolve_id, which
    reads attributes by name rather than assuming a single-column PK; a
    commit that inserts one recipient row must produce exactly one
    "announcements" signal, not zero and not one per column."""
    with session_factory() as session:
        ack = _make_ack(session)
        session.flush()  # assigns ack.id before the recipient needs it as an FK
        session.commit()
        ack_id = ack.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        ack = session.get(AcknowledgementOrmModel, ack_id)
        _make_recipient(session, ack, user_id=7)
        session.commit()

    # A new recipient on an *existing* acknowledgement is never read as the
    # acknowledgement itself appearing: same child-row rule as an order
    # gaining a new item, so the forced action is "updated".
    assert await _signals(fake_redis) == [_announcements_signal(ack_id, "updated")]


async def test_acknowledgement_recipient_acknowledge_signals_its_acknowledgement_as_updated(
    session_factory, fake_redis
):
    """Setting acknowledged_at (the AcknowledgeAnnouncement path) is an
    UPDATE on the composite-PK row: same id resolution as the create
    case above, exercised on session.dirty instead of session.new."""
    with session_factory() as session:
        ack = _make_ack(session)
        session.flush()
        _make_recipient(session, ack, user_id=7)
        session.commit()
        ack_id = ack.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        recipient = session.get(AcknowledgementRecipientOrmModel, (ack_id, 7))
        recipient.acknowledged_at = datetime.now(UTC)
        session.commit()

    assert await _signals(fake_redis) == [_announcements_signal(ack_id, "updated")]


async def test_acknowledgement_recipient_delete_signals_updated_not_deleted(
    session_factory, fake_redis
):
    """Deleting one recipient row (e.g. cascade from the acknowledgement
    itself being removed) must never read as "the acknowledgement was
    deleted" on its own: same child-row rule as deleting one order item."""
    with session_factory() as session:
        ack = _make_ack(session)
        session.flush()
        _make_recipient(session, ack, user_id=7)
        session.commit()
        ack_id = ack.id

    await _drain()

    fake_redis.published.clear()

    with session_factory() as session:
        recipient = session.get(AcknowledgementRecipientOrmModel, (ack_id, 7))
        session.delete(recipient)
        session.commit()

    assert await _signals(fake_redis) == [_announcements_signal(ack_id, "updated")]


async def test_acknowledgement_and_its_recipient_created_together_dedupe_to_created(
    session_factory, fake_redis
):
    """Same dedupe rule as orders: the acknowledgement's own real
    "created" action wins over the forced "updated" from its new
    recipient row in the same transaction."""
    with session_factory() as session:
        ack = _make_ack(session)
        session.flush()  # assigns ack.id without ending the transaction
        _make_recipient(session, ack, user_id=7)
        session.commit()
        ack_id = ack.id

    assert await _signals(fake_redis) == [_announcements_signal(ack_id, "created")]


# ── Bulk scheduling writes ────────────────────────────────────────────


@pytest.fixture
async def async_session_factory():
    """Async counterpart of session_factory, for repository methods that
    only exist on AsyncSession. Same private tracked Session subclass, so
    the listeners stay confined to this test."""

    class _TrackedSession(Session):
        pass

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, sync_session_class=_TrackedSession, expire_on_commit=False)
    register_change_tracking(factory)
    yield factory
    await engine.dispose()


async def _seed_two_scheduled_orders(factory) -> tuple[int, int, int, int]:
    """One lot with one position holding two production orders. Returns
    (lot_id, position_id, first_order_id, second_order_id)."""
    async with factory() as session:
        lot = ProductionLotOrmModel(
            lot_number="LOT-BULK",
            quantity=1.0,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            created=date.today(),
        )
        session.add(lot)
        await session.flush()
        position = LotPositionOrmModel(
            created=date.today(), sequence=1, quantity=1.0, creator_id=1, lot_id=lot.id
        )
        session.add(position)
        await session.flush()
        orders = [
            ProductionOrderOrmModel(
                created=date.today(),
                production_order_number=f"PO-BULK-{n}",
                quantity=1.0,
                queue_sequence=n,
                creator_id=1,
                lot_position_id=position.id,
            )
            for n in (1, 2)
        ]
        session.add_all(orders)
        await session.commit()
        return lot.id, position.id, orders[0].id, orders[1].id


async def test_bulk_schedule_write_signals_changed_orders_only(async_session_factory, fake_redis):
    """save_schedule writes through the ORM rows, so live sync
    still sees the orders whose dates it changed, and an order written back
    unchanged stays silent, exactly like a per-row save."""
    lot_id, position_id, changed_id, unchanged_id = await _seed_two_scheduled_orders(
        async_session_factory
    )
    await _drain()
    fake_redis.published.clear()

    changed = make_order(changed_id, lot_id, queue_sequence=1)
    changed.lot_position_id = position_id
    changed.planned_start = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)
    changed.planned_end = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
    unchanged = make_order(unchanged_id, lot_id, queue_sequence=2)
    unchanged.lot_position_id = position_id

    async with async_session_factory() as session:
        await SqlAlchemyProductionOrderRepository(session).save_schedule([changed, unchanged])
        await session.commit()

    assert await _signals(fake_redis) == [
        {
            "resource": LiveResource.PRODUCTION_ORDERS,
            "id": changed_id,
            "action": "updated",
            "actor_id": None,
        },
        {
            "resource": LiveResource.PRODUCTION_LOTS,
            "id": lot_id,
            "action": "updated",
            "actor_id": None,
        },
    ]
    async with async_session_factory() as session:
        row = await session.get(ProductionOrderOrmModel, changed_id)
        assert row is not None
        assert row.planned_end is not None
        assert row.planned_end.replace(tzinfo=UTC) == changed.planned_end


async def test_planning_field_write_signals_changed_orders_only(async_session_factory, fake_redis):
    """save_planning_fields writes through the ORM rows like save_schedule,
    so live sync sees the order whose window it changed and that order's
    lot, and an unchanged order stays silent."""
    lot_id, _, changed_id, unchanged_id = await _seed_two_scheduled_orders(async_session_factory)
    await _drain()
    fake_redis.published.clear()

    planned_start = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)
    planned_end = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
    async with async_session_factory() as session:
        await SqlAlchemyProductionOrderRepository(session).save_planning_fields(
            [
                ProductionOrderPlanningFields(
                    order_id=changed_id,
                    planned_start=planned_start,
                    planned_end=planned_end,
                    planned_by_id=None,
                    pinned_when_read=False,
                ),
                ProductionOrderPlanningFields(
                    order_id=unchanged_id,
                    planned_start=None,
                    planned_end=None,
                    planned_by_id=None,
                    pinned_when_read=False,
                ),
            ]
        )
        await session.commit()

    assert await _signals(fake_redis) == [
        {
            "resource": LiveResource.PRODUCTION_ORDERS,
            "id": changed_id,
            "action": "updated",
            "actor_id": None,
        },
        {
            "resource": LiveResource.PRODUCTION_LOTS,
            "id": lot_id,
            "action": "updated",
            "actor_id": None,
        },
    ]
    async with async_session_factory() as session:
        row = await session.get(ProductionOrderOrmModel, changed_id)
        assert row is not None
        assert row.planned_end is not None
        assert row.planned_end.replace(tzinfo=UTC) == planned_end


async def test_bulk_position_forecast_write_signals_its_lot(async_session_factory, fake_redis):
    lot_id, position_id, _, _ = await _seed_two_scheduled_orders(async_session_factory)
    await _drain()
    fake_redis.published.clear()

    async with async_session_factory() as session:
        await SqlAlchemyProductionLotRepository(session).save_position_forecasts(
            [
                ExternalForecast(
                    position_id=position_id,
                    planned_pickup_date=date(2026, 11, 3),
                    planned_delivery_date=date(2026, 11, 5),
                ),
                ExternalForecast(
                    position_id=999_999,
                    planned_pickup_date=None,
                    planned_delivery_date=None,
                ),
            ]
        )
        await session.commit()

    assert await _signals(fake_redis) == [
        {
            "resource": LiveResource.PRODUCTION_LOTS,
            "id": lot_id,
            "action": "updated",
            "actor_id": None,
        }
    ]
    async with async_session_factory() as session:
        row = await session.get(LotPositionOrmModel, position_id)
        assert row is not None
        assert row.planned_delivery_date == date(2026, 11, 5)
