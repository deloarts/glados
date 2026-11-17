"""
A machine is archived only with nothing in process on it: a queued,
in-progress or paused production order keeps the archive refused with a 409
that counts them, since archiving would take those orders off the planning
and queue boards. The machine read carries the count, so the archive button
can say why it is disabled.
"""

from sqlalchemy.orm import Session

from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.conftest import auth_headers
from tests.integration.lifecycle_matrix._shapes import WEB
from tests.integration.test_api_production_machine_status import MACHINES_BASE
from tests.integration.test_api_production_machine_status import _seed_lot_position
from tests.integration.test_api_production_machine_status import _seed_machine
from tests.integration.test_api_production_machine_status import _seed_order
from tests.integration.test_api_production_state_machine import _seed_lot_with_internal_order


async def test_a_machine_with_live_orders_is_not_archived(db: Session, client, create_user) -> None:
    user = await create_user(permissions=[Permission.WRITE_MACHINES])
    headers = await auth_headers(user)
    position = await _seed_lot_position(db, user.id, lot_number="ARCHIVE-LOT-1")
    machine = await _seed_machine(db, user.id, "ARCHIVE-BUSY")
    # The seed helper starts every order, so it is in progress.
    await _seed_order(
        db,
        user.id,
        number="PO-ARCH-R",
        machine_id=machine.id,
        lot_position_id=position.id,
        status=ProductionOrderStatus.IN_PROGRESS,
    )

    read = await client.get(f"{MACHINES_BASE}/{machine.id}", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["live_order_count"] == 1

    resp = await client.post(f"{MACHINES_BASE}/{machine.id}/archive", headers=headers)

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "ProductionMachineArchiveBlockedError"
    assert "1 production order" in resp.json()["detail"]
    reread = await client.get(f"{MACHINES_BASE}/{machine.id}", headers=headers)
    assert reread.json()["archived"] is False


async def test_a_machine_without_live_orders_is_archived(db: Session, client, create_user) -> None:
    user = await create_user(permissions=[Permission.WRITE_MACHINES])
    headers = await auth_headers(user)
    machine = await _seed_machine(db, user.id, "ARCHIVE-IDLE")

    resp = await client.post(f"{MACHINES_BASE}/{machine.id}/archive", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["archived"] is True
    assert resp.json()["live_order_count"] == 0


async def test_an_archived_machine_takes_no_production_order(db: Session, auth_client) -> None:
    """The writers that queue an order on a machine refuse an archived one
    under the machine's queue lock, the lock the archive takes before it
    counts, so no order lands on a machine archived meanwhile."""
    client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
    _lot, _position, order = await _seed_lot_with_internal_order(db, 1, with_machine=True)
    assert order is not None
    archived = await _seed_machine(db, 1, "ARCHIVE-GONE")
    archived.archived = True
    await SqlAlchemyProductionMachineRepository(db).save(archived)
    await db.commit()

    resp = await client.put(
        f"{WEB}/production-orders/{order.id}/machine", json={"machine_id": archived.id}
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "ProductionMachineArchivedError"
