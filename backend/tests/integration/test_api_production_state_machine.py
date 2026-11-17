"""
HTTP-level coverage for the production state machine: pins the
exception->status mapping, the permission dependencies and the request
schemas for every state-transition endpoint this hardening pass touches.
Test-only: no source behavior is defined here, this is the boundary
verification that the unit tests' domain exceptions really do surface as
the intended status codes.

Two cases per endpoint: a terminal/invalid-state case and a
missing-permission case. The graph (lot -> position -> step ->
production order) is seeded directly through the repositories via the `db`
fixture, since building it over HTTP would be several requests of setup
per assertion, and only the transition under test is driven over HTTP.

Terminal-lot assign and start return 422; reassign, reorder, and updating
a terminal lot return 422 rather than 403; unassign and provision without
write:lots return 403; and lot structural writes without write:lots return
403.
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy import select

from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.production import (
    AdminProductionSettingsOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration import _lifecycle_seed as seed
from tests.integration._lot_facts import give_lot_facts
from tests.integration._production_order_facts import give_production_order_facts
from tests.integration.conftest import auth_headers

ORDERS = f"{API_WEB}/production-orders"
LOTS = f"{API_WEB}/production-lots"

_number_seq = itertools.count(1)


@pytest.fixture(autouse=True)
async def _seed_production_settings(db):
    """The shared conftest seeds only the settings domains its own tests
    read; a successful queue reorder additionally walks the machine
    calendar, which reads AdminProductionSettings. Seeded locally rather
    than in the shared conftest so no other integration test's fixture
    surface changes."""
    if not await db.scalar(select(AdminProductionSettingsOrmModel).filter_by(id=1).limit(1)):
        db.add(
            AdminProductionSettingsOrmModel(
                id=1,
                production_order_number_format="PO-{seq:04d}",
                default_weekly_hours={str(d): 480 for d in range(5)},
                default_external_lead_days=0,
                response_time_days=0,
                require_qa=False,
                default_inspection_method_id=None,
            )
        )
        await db.commit()


async def _seed_lot_with_internal_order(
    db,
    creator_id: int,
    *,
    lot_status: LotStatus | None = None,
    order_status: ProductionOrderStatus = ProductionOrderStatus.QUEUED,
    position_kind: LotPositionKind = LotPositionKind.INTERNAL,
    queue_sequence: int = 1,
    with_machine: bool = False,
) -> tuple[ProductionLot, LotPosition, ProductionOrder | None]:
    """One lot -> one position -> one production order, the smallest graph
    every transition below needs. `lot_status` / `order_status` are the two
    knobs the terminal-state cases turn; a given lot status becomes the
    intent it stands for and must be what the facts derive, and without one
    the lot takes whatever its position and order give it. An UNASSIGNED
    position gets no production order, and an EXTERNAL one a pending
    purchase line instead. `with_machine=True` additionally
    assigns a real machine to the order. Most transitions here don't need
    one (they fail on a permission/state check first), but an actual
    successful Start does (an unassigned INTERNAL position rejects it)."""
    seq = next(_number_seq)
    project = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0,
            created=datetime.now(UTC),
            creator_id=creator_id,
            project_number=f"P-SM-{seq}",
        )
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=f"State machine part {seq}",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=f"LN-SM-{seq}",
            quantity=10.0,
            status=lot_status or LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
            # Rework/alteration run: exempt from sequence-1 raw-material
            # gating, which is not what these tests are about.
            source_made_item_id=made_item.id,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=position_kind,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    if position_kind == LotPositionKind.EXTERNAL.value:
        purchase = await seed.order(db, "draft")
        await seed.line(db, purchase, "pending", at=await db.get(LotPositionOrmModel, position.id))
    if position_kind != LotPositionKind.INTERNAL.value:
        await give_lot_facts(db, lot.id, exact=lot_status is not None)
        await db.commit()
        return lot, position, None
    machine_id = None
    if with_machine:
        machine = await SqlAlchemyProductionMachineRepository(db).save(
            ProductionMachine(
                id=0,
                created=date.today(),
                changed=None,
                changes=[],
                archived=False,
                internal_name=f"SM-MILL-{seq}",
                vendor="Contoso",
                model="VF-2",
                fabrication_method_ids=[],
                max_part_dimension=None,
                note=None,
                creator_id=creator_id,
            )
        )
        await db.commit()
        machine_id = machine.id
    order = await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"PO-SM-{seq}",
            status=order_status,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=queue_sequence,
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine_id,
            lot_position_id=position.id,
        )
    )
    await give_production_order_facts(db, order.id)
    await give_lot_facts(db, lot.id, exact=lot_status is not None)
    await db.commit()
    return lot, position, order


async def _seed_unassigned_position(db, creator_id: int, *, lot_status: LotStatus):
    """A lot whose single position is still UNASSIGNED, the starting point
    for the two assign endpoints."""
    lot, position, _ = await _seed_lot_with_internal_order(
        db, creator_id, lot_status=lot_status, position_kind=LotPositionKind.UNASSIGNED
    )
    return lot, position


# ── POST /production-orders/{id}/start ────────────────────────────────


class TestStartProductionOrder:
    async def test_rejects_order_on_a_canceled_lot(self, db, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        _, _, order = await _seed_lot_with_internal_order(db, 1, lot_status=LotStatus.CANCELED)
        response = await client.post(f"{ORDERS}/{order.id}/start", json={})
        assert response.status_code == 422

    async def test_requires_permission(self, db, auth_client):
        client = await auth_client(permissions=[])
        _, _, order = await _seed_lot_with_internal_order(db, 1)
        response = await client.post(f"{ORDERS}/{order.id}/start", json={})
        assert response.status_code == 403


# ── POST /production-orders/{id}/pause ────────────────────────────────


class TestPauseProductionOrder:
    async def test_rejects_a_queued_order(self, db, auth_client):
        """QUEUED -> PAUSED is not a legal transition (only IN_PROGRESS is)."""
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        _, _, order = await _seed_lot_with_internal_order(db, 1)
        response = await client.post(f"{ORDERS}/{order.id}/pause", json={})
        assert response.status_code == 422

    async def test_requires_permission(self, db, auth_client):
        client = await auth_client(permissions=[])
        _, _, order = await _seed_lot_with_internal_order(
            db, 1, order_status=ProductionOrderStatus.IN_PROGRESS
        )
        response = await client.post(f"{ORDERS}/{order.id}/pause", json={})
        assert response.status_code == 403


# ── POST /production-orders/{id}/start started_operator_id round-trip ──


class TestStartProductionOrderSetsStartedOperator:
    async def test_start_sets_started_operator_id_and_exposes_started_operator(
        self, db, client, create_user
    ):
        operator = await create_user(
            username="sm-operator",
            email="sm-operator@example.com",
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
        )
        _, _, order = await _seed_lot_with_internal_order(db, operator.id, with_machine=True)

        response = await client.post(
            f"{ORDERS}/{order.id}/start", json={}, headers=await auth_headers(operator)
        )

        assert response.status_code == 200
        body = response.json()
        assert body["started_operator_id"] == operator.id
        assert body["started_operator"]["username"] == "sm-operator"

    async def test_pause_keeps_started_operator_id(self, db, client, create_user):
        operator = await create_user(
            username="sm-pauser",
            email="sm-pauser@example.com",
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
        )
        _, _, order = await _seed_lot_with_internal_order(db, operator.id, with_machine=True)
        await client.post(
            f"{ORDERS}/{order.id}/start", json={}, headers=await auth_headers(operator)
        )

        response = await client.post(
            f"{ORDERS}/{order.id}/pause", json={}, headers=await auth_headers(operator)
        )

        assert response.status_code == 200
        assert response.json()["started_operator_id"] == operator.id

    async def test_resuming_with_a_different_operator_overwrites_started_operator_id(
        self, db, client, create_user
    ):
        first_operator = await create_user(
            username="sm-first",
            email="sm-first@example.com",
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
        )
        second_operator = await create_user(
            username="sm-second",
            email="sm-second@example.com",
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
        )
        _, _, order = await _seed_lot_with_internal_order(db, first_operator.id, with_machine=True)
        await client.post(
            f"{ORDERS}/{order.id}/start", json={}, headers=await auth_headers(first_operator)
        )
        await client.post(
            f"{ORDERS}/{order.id}/pause", json={}, headers=await auth_headers(first_operator)
        )

        # A personal account names no one but itself, so the second operator
        # resumes under their own account.
        refused = await client.post(
            f"{ORDERS}/{order.id}/start",
            json={"operator_id": second_operator.id},
            headers=await auth_headers(first_operator),
        )
        response = await client.post(
            f"{ORDERS}/{order.id}/start", json={}, headers=await auth_headers(second_operator)
        )

        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "OperatorNotAssignedError"
        assert response.status_code == 200
        body = response.json()
        assert body["started_operator_id"] == second_operator.id
        assert body["started_operator"]["username"] == "sm-second"


# ── POST /production-orders/{id}/start, pool resolution ────────────────


class TestStartProductionOrderResolvesPoolQueueSequence:
    """Regression: resolving a pool-assigned order onto a concrete machine
    at start time must not keep the order's pool-scope queue_sequence,
    the target machine may already have a live order at that same number,
    and the DB partial unique index (uq_production_order_queue_sequence_
    machine) rejects the flush. Enforced on
    SQLite too (production_order_model.py's sqlite_where), so this is a
    genuine end-to-end reproduction, not just a value assertion."""

    async def test_starting_onto_an_occupied_machine_resequences_instead_of_colliding(
        self, db, client, create_user
    ):
        user = await create_user(
            username="sm-pool-start",
            email="sm-pool-start@example.com",
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
        )
        # An order already live on the target machine, holding
        # queue_sequence 1 in that machine's own scope.
        _, _, occupant = await _seed_lot_with_internal_order(
            db, user.id, with_machine=True, queue_sequence=1
        )
        machine_id = occupant.machine_id
        pool = await SqlAlchemyMachinePoolRepository(db).save(
            MachinePool(
                id=0,
                created=date.today(),
                changed=None,
                changes=[],
                archived=False,
                name="SM start pool",
                machine_ids=[machine_id],
                note=None,
                creator_id=user.id,
            )
        )
        await db.commit()
        # A pool-assigned, not-yet-resolved order carrying the SAME
        # queue_sequence in its own (pool) scope: the collision this
        # test reproduces.
        _, _, order = await _seed_lot_with_internal_order(db, user.id, queue_sequence=1)
        order_repo = SqlAlchemyProductionOrderRepository(db)
        order.machine_pool_id = pool.id
        await order_repo.save(order)
        await db.commit()

        response = await client.post(
            f"{ORDERS}/{order.id}/start",
            json={"machine_id": machine_id},
            headers=await auth_headers(user),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == ProductionOrderStatus.IN_PROGRESS.value
        assert body["machine_id"] == machine_id
        assert body["machine_pool_id"] == pool.id  # provenance kept
        assert body["queue_sequence"] != occupant.queue_sequence
        assert body["queue_sequence"] == 2


# ── POST /production-orders/{id}/cancel ───────────────────────────────


class TestCancelProductionOrder:
    async def test_rejects_an_already_canceled_order(self, db, auth_client, create_user):
        user = await create_user(
            username="canceller",
            email="canceller@example.com",
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.MANAGE_PRODUCTION_ORDERS],
        )
        client = await auth_client(
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.MANAGE_PRODUCTION_ORDERS],
            username="canceller2",
            email="canceller2@example.com",
        )
        _, _, order = await _seed_lot_with_internal_order(
            db, user.id, order_status=ProductionOrderStatus.CANCELED
        )
        response = await client.post(
            f"{ORDERS}/{order.id}/cancel", json={"expected_edit_version": order.edit_version}
        )
        assert response.status_code == 422

    async def test_non_creator_without_manage_is_forbidden(self, db, auth_client, create_user):
        owner = await create_user(
            username="owner", email="owner@example.com", permissions=[Permission.WRITE_LOTS]
        )
        client = await auth_client(
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
            username="stranger",
            email="stranger@example.com",
        )
        _, _, order = await _seed_lot_with_internal_order(db, owner.id)
        response = await client.post(
            f"{ORDERS}/{order.id}/cancel", json={"expected_edit_version": order.edit_version}
        )
        assert response.status_code == 403


# ── POST /production-orders/{id}/split ────────────────────────────────


class TestSplitProductionOrder:
    async def test_rejects_a_non_queued_order(self, db, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        _, _, order = await _seed_lot_with_internal_order(
            db, 1, order_status=ProductionOrderStatus.IN_PROGRESS
        )
        response = await client.post(f"{ORDERS}/{order.id}/split", json={"quantities": [6.0, 4.0]})
        # ProductionOrderNotSplittableError -> 409.
        assert response.status_code == 409

    async def test_requires_permission(self, db, auth_client):
        client = await auth_client(permissions=[])
        _, _, order = await _seed_lot_with_internal_order(db, 1)
        response = await client.post(f"{ORDERS}/{order.id}/split", json={"quantities": [6.0, 4.0]})
        assert response.status_code == 403


# ── PUT /production-orders/{id}/machine ───────────────────────────────


class TestReassignProductionOrderMachine:
    async def test_completed_order_is_a_state_conflict_not_a_permission_error(
        self, db, auth_client
    ):
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        _, _, order = await _seed_lot_with_internal_order(
            db, 1, order_status=ProductionOrderStatus.COMPLETED
        )
        response = await client.put(f"{ORDERS}/{order.id}/machine", json={})
        assert response.status_code == 422

    async def test_requires_permission(self, db, auth_client):
        client = await auth_client(permissions=[])
        _, _, order = await _seed_lot_with_internal_order(db, 1)
        response = await client.put(f"{ORDERS}/{order.id}/machine", json={})
        assert response.status_code == 403


# ── PUT /production-orders/machines/unassigned/queue ──────────────────


class TestReorderProductionOrders:
    async def test_completed_order_in_the_list_is_a_state_conflict(self, db, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        _, _, order = await _seed_lot_with_internal_order(
            db, 1, order_status=ProductionOrderStatus.COMPLETED
        )
        response = await client.put(
            f"{ORDERS}/machines/unassigned/queue",
            json={"ordered_production_order_ids": [order.id]},
        )
        assert response.status_code == 422

    async def test_duplicate_ids_are_rejected(self, db, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        _, _, order = await _seed_lot_with_internal_order(db, 1)
        response = await client.put(
            f"{ORDERS}/machines/unassigned/queue",
            json={"ordered_production_order_ids": [order.id, order.id]},
        )
        assert response.status_code == 422

    async def test_adjacent_swap_succeeds(self, db, auth_client):
        """A plain adjacent swap goes through end to end, despite the
        reorder's concurrency guards."""
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        _, _, first = await _seed_lot_with_internal_order(db, 1, queue_sequence=1)
        _, _, second = await _seed_lot_with_internal_order(db, 1, queue_sequence=2)

        response = await client.put(
            f"{ORDERS}/machines/unassigned/queue",
            json={"ordered_production_order_ids": [second.id, first.id]},
        )

        assert response.status_code == 200
        by_id = {o["id"]: o["queue_sequence"] for o in response.json()}
        assert by_id[second.id] == 1
        assert by_id[first.id] == 2

    async def test_requires_permission(self, db, auth_client):
        client = await auth_client(permissions=[])
        _, _, order = await _seed_lot_with_internal_order(db, 1)
        response = await client.put(
            f"{ORDERS}/machines/unassigned/queue",
            json={"ordered_production_order_ids": [order.id]},
        )
        assert response.status_code == 403


# ── PATCH /production-orders/{id} ─────────────────────────────────────


class TestUpdateProductionOrder:
    async def test_rejects_an_edit_on_a_completed_order(self, db, auth_client):
        client = await auth_client(
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.MANAGE_PRODUCTION_ORDERS]
        )
        _, _, order = await _seed_lot_with_internal_order(
            db, 1, order_status=ProductionOrderStatus.COMPLETED
        )
        response = await client.patch(
            f"{ORDERS}/{order.id}",
            json={"note": "late annotation", "expected_edit_version": order.edit_version},
        )
        assert response.status_code == 422

    async def test_requires_permission(self, db, auth_client):
        client = await auth_client(permissions=[])
        _, _, order = await _seed_lot_with_internal_order(db, 1)
        response = await client.patch(
            f"{ORDERS}/{order.id}",
            json={"note": "nope", "expected_edit_version": order.edit_version},
        )
        assert response.status_code == 403


# ── POST /production-lots/{id}/positions/{pid}/assign-internal ────────


class TestAssignInternalPosition:
    async def test_rejects_assignment_on_a_canceled_lot(self, db, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        lot, position = await _seed_unassigned_position(db, 1, lot_status=LotStatus.CANCELED)
        response = await client.post(
            f"{LOTS}/{lot.id}/positions/{position.id}/assign-internal",
            json={"orders": [{"quantity": 5.0}]},
        )
        assert response.status_code == 422

    async def test_requires_permission(self, db, auth_client):
        client = await auth_client(permissions=[])
        lot, position = await _seed_unassigned_position(db, 1, lot_status=LotStatus.DRAFT)
        response = await client.post(
            f"{LOTS}/{lot.id}/positions/{position.id}/assign-internal",
            json={"orders": [{"quantity": 5.0}]},
        )
        assert response.status_code == 403


# ── POST /production-lots/{id}/positions/{pid}/assign ─────────────────


class TestAssignExternalPosition:
    async def test_rejects_assignment_on_a_canceled_lot(self, db, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_LOTS, Permission.WRITE_ORDERS])
        lot, position = await _seed_unassigned_position(db, 1, lot_status=LotStatus.CANCELED)
        response = await client.post(
            f"{LOTS}/{lot.id}/positions/{position.id}/assign",
            json={"order_id": 1, "unit": "pcs"},
        )
        assert response.status_code == 422


# ── DELETE /production-lots/{id}/positions/{pid}/assign ───────────────


class TestUnassignExternalPosition:
    async def test_requires_write_lots(self, db, auth_client):
        """Unassigning deletes a real OrderItem row, so it requires
        write:lots."""
        client = await auth_client(permissions=[])
        lot, position, _ = await _seed_lot_with_internal_order(
            db, 1, position_kind=LotPositionKind.EXTERNAL
        )
        response = await client.delete(f"{LOTS}/{lot.id}/positions/{position.id}/assign")
        assert response.status_code == 403


# ── POST /production-lots/{id}/positions/{pid}/provisions ─────────────


class TestRecordLotPositionProvision:
    async def test_requires_write_lots(self, db, auth_client):
        """Recording a provision requires write:lots."""
        client = await auth_client(permissions=[])
        lot, position, _ = await _seed_lot_with_internal_order(
            db, 1, position_kind=LotPositionKind.EXTERNAL
        )
        response = await client.post(
            f"{LOTS}/{lot.id}/positions/{position.id}/provisions",
            json={"quantity": 1.0, "provision_date": "2026-01-02"},
        )
        assert response.status_code == 403


# ── Lot structural mutations ──────────────────────────────────────────


class TestLotStructuralMutations:
    async def test_add_step_requires_write_lots(self, db, auth_client):
        client = await auth_client(permissions=[])
        lot, position, _ = await _seed_lot_with_internal_order(db, 1)
        response = await client.post(
            f"{LOTS}/{lot.id}/steps",
            json={"position_id": position.id, "fabrication_method_id": 1},
        )
        assert response.status_code == 403

    async def test_add_step_on_a_terminal_lot_is_a_conflict_for_a_permitted_actor(
        self, db, auth_client
    ):
        """The permission-first ordering must not have swallowed the 409."""
        client = await auth_client(permissions=[Permission.WRITE_LOTS])
        lot, position, _ = await _seed_lot_with_internal_order(db, 1, lot_status=LotStatus.CANCELED)
        response = await client.post(
            f"{LOTS}/{lot.id}/steps",
            json={"position_id": position.id, "fabrication_method_id": 1},
        )
        assert response.status_code == 409

    async def test_regroup_positions_requires_write_lots(self, db, auth_client):
        client = await auth_client(permissions=[])
        lot, _, _ = await _seed_lot_with_internal_order(db, 1)
        response = await client.put(f"{LOTS}/{lot.id}/positions", json={"groups": [[1]]})
        assert response.status_code == 403

    async def test_replace_structure_requires_write_lots(self, db, auth_client):
        client = await auth_client(permissions=[])
        lot, _, _ = await _seed_lot_with_internal_order(db, 1)
        response = await client.put(
            f"{LOTS}/{lot.id}/structure",
            json={"positions": [{"steps": [{"role": "fabrication", "fabrication_method_id": 1}]}]},
        )
        assert response.status_code == 403


# ── POST /production-orders/{id}/assessment ───────────────────────────


class TestRecordManufacturingAssessment:
    async def test_recorded_assessment_is_persisted(self, db, auth_client):
        client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        _, _, order = await _seed_lot_with_internal_order(
            db, 1, order_status=ProductionOrderStatus.COMPLETED
        )
        await db.commit()

        response = await client.post(
            f"{ORDERS}/{order.id}/assessment",
            json={"actual_minutes_per_piece": 7, "complexity": "normal"},
        )
        assert response.status_code == 200, response.text

        reread = await client.get(f"{ORDERS}/{order.id}/assessment")
        assert reread.status_code == 200
        assert reread.json()["actual_minutes_per_piece"] == 7
