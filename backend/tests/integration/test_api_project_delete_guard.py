"""
A project with live work is not deleted: the repository counts the project's
unfinished lots, production orders, order lines and demands, and
DELETE /projects/{id} answers 409 with those counts instead of canceling
anything. Finished work is seeded in every finished status of every kind, so
a status missing from the repository's finished sets fails here. The rows
are written through the ORM with statuses that agree with their facts and
intents, so they also hold once the lifecycle reconciler checks every test's
rows.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model import (
    OrderItemDeliveryOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_completion_model import (
    ProductionOrderCompletionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.project_work_repository import (
    SqlAlchemyProjectWork,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from tests.integration._edit_versions import row_version

NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
PROJECTS = "/api/v1/web/projects"
MANAGER = ["write:projects", "manage:projects"]

LIVE_WORK = ProjectLiveWork(
    lots=2,
    production_orders=1,
    order_lines=1,
    bought_demands=1,
    made_demands=1,
    source_demands=1,
)


async def _project(db: AsyncSession, number: str) -> Project:
    saved = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=NOW, creator_id=1, project_number=number)
    )
    await db.commit()
    return saved


async def _add[T](db: AsyncSession, row: T) -> T:
    db.add(row)
    await db.flush()
    return row


async def _lot(db: AsyncSession, project_id: int, number: str, status: str, **values: Any):
    return await _add(
        db,
        ProductionLotOrmModel(
            created=NOW,
            lot_number=number,
            quantity=values.pop("quantity", 10.0),
            status=status,
            creator_id=1,
            made_item_id=1,
            project_id=project_id,
            **values,
        ),
    )


async def _position(db: AsyncSession, lot_id: int, kind: str, status: str, completed: float):
    return await _add(
        db,
        LotPositionOrmModel(
            created=NOW,
            sequence=1,
            kind=kind,
            status=status,
            quantity=10.0,
            quantity_completed=completed,
            creator_id=1,
            lot_id=lot_id,
        ),
    )


async def _production_order(db: AsyncSession, position_id: int, number: str, **values: Any):
    return await _add(
        db,
        ProductionOrderOrmModel(
            created=NOW,
            production_order_number=number,
            quantity=10.0,
            quantity_completed=values.pop("quantity_completed", 0.0),
            creator_id=1,
            lot_position_id=position_id,
            **values,
        ),
    )


async def _order(db: AsyncSession, number: str, status: str, **values: Any):
    return await _add(
        db,
        OrderOrmModel(
            order_number=number, created=NOW, status=status, creator_id=1, supplier_id=1, **values
        ),
    )


async def _line(db: AsyncSession, order_id: int, project_id: int, **values: Any):
    return await _add(
        db,
        OrderItemOrmModel(
            created=NOW,
            quantity=4.0,
            quantity_delivered=values.pop("quantity_delivered", 0.0),
            unit="pcs",
            creator_id=1,
            order_id=order_id,
            supplier_id=1,
            line_type="BOUGHT",
            bought_item_id=1,
            project_id=project_id,
            **values,
        ),
    )


def _bought_demand(project_id: int, **values: Any) -> BoughtItemDemandItemOrmModel:
    return BoughtItemDemandItemOrmModel(
        created=NOW.date(),
        quantity=2.0,
        unit="pcs",
        creator_id=1,
        item_id=1,
        project_id=project_id,
        **values,
    )


def _made_demand(project_id: int, **values: Any) -> MadeItemDemandItemOrmModel:
    return MadeItemDemandItemOrmModel(
        created=NOW.date(),
        quantity=2.0,
        unit="pcs",
        creator_id=1,
        made_item_id=1,
        project_id=project_id,
        **values,
    )


def _source_demand(project_id: int, lot_id: int, **values: Any) -> SourceItemDemandItemOrmModel:
    """A lot's material demand; a lot has at most one."""
    return SourceItemDemandItemOrmModel(
        created=NOW.date(),
        quantity=3.0,
        unit="kg",
        creator_id=1,
        lot_id=lot_id,
        project_id=project_id,
        **values,
    )


async def _seed_live_work(db: AsyncSession, project_id: int, other_project_id: int) -> None:
    """Two live lots (a draft one, and a planned one whose position has a
    queued production order), one live order line, one live demand per
    family, and a live demand of another project."""
    await _lot(db, project_id, "LOT-DRAFT", "draft")
    planned = await _lot(db, project_id, "LOT-PLANNED", "planned")
    position = await _position(db, planned.id, "internal", "ordered_or_queued", 0.0)
    await _production_order(db, position.id, "PO-QUEUED", status="queued")

    order = await _order(db, "ORD-DRAFT", "draft")
    await _line(db, order.id, project_id, status="pending")

    await _add(db, _bought_demand(project_id, status="open"))
    await _add(db, _bought_demand(other_project_id, status="open"))
    await _add(db, _made_demand(project_id, status="open"))
    await _add(db, _source_demand(project_id, planned.id, status="open"))
    await db.commit()


async def _seed_finished_work(db: AsyncSession, project_id: int) -> None:
    """One row in every finished status of every kind: lots completed,
    canceled and scrapped; production orders completed and canceled; order
    lines delivered and canceled; demands of the three families fulfilled
    and canceled."""
    canceled = await _lot(db, project_id, "LOT-CANCELED", "canceled", canceled_at=NOW)
    await _lot(db, project_id, "LOT-SCRAPPED", "scrapped", quantity=0.0, quantity_scrapped=10.0)
    completed = await _lot(db, project_id, "LOT-COMPLETED", "completed", completed_at=NOW)
    position = await _position(db, completed.id, "internal", "completed", 10.0)
    done = await _production_order(
        db,
        position.id,
        "PO-COMPLETED",
        status="completed",
        quantity_completed=10.0,
        actual_start=NOW,
        actual_end=NOW,
    )
    await _add(
        db,
        ProductionOrderCompletionOrmModel(
            created=NOW,
            production_order_id=done.id,
            quantity=10.0,
            quantity_accepted=10.0,
            quantity_rejected=0.0,
            completion_date=NOW.date(),
            operator_id=1,
            recorded_by_id=1,
        ),
    )
    await _production_order(db, position.id, "PO-CANCELED", status="canceled", canceled_at=NOW)

    order = await _order(db, "ORD-DELIVERED", "delivered", ordered_date=NOW, delivery_date=NOW)
    delivered = await _line(
        db,
        order.id,
        project_id,
        status="delivered",
        quantity_delivered=4.0,
        ordered_date=NOW,
        delivery_date=NOW,
    )
    await _add(
        db,
        OrderItemDeliveryOrmModel(
            created=NOW, order_item_id=delivered.id, quantity=4.0, delivery_date=NOW
        ),
    )
    await _line(db, order.id, project_id, status="canceled", canceled_at=NOW)

    await _add(db, _bought_demand(project_id, status="fulfilled", fulfilled_manually_at=NOW))
    await _add(db, _bought_demand(project_id, status="canceled", canceled_at=NOW))
    await _add(db, _made_demand(project_id, status="fulfilled", fulfilled_manually_at=NOW))
    await _add(db, _made_demand(project_id, status="canceled", canceled_at=NOW))
    await _add(
        db, _source_demand(project_id, completed.id, status="fulfilled", fulfilled_manually_at=NOW)
    )
    await _add(
        db,
        _source_demand(project_id, canceled.id, status="canceled", canceled_at=NOW),
    )
    await db.commit()


async def test_finished_work_of_every_kind_and_status_counts_nothing(db: AsyncSession) -> None:
    project = await _project(db, "P-DONE")
    await _seed_finished_work(db, project.id)

    assert await SqlAlchemyProjectWork(db).get_live_work(project.id) == ProjectLiveWork()


async def test_the_repository_counts_only_the_projects_unfinished_work(db: AsyncSession) -> None:
    project = await _project(db, "P-LIVE")
    other = await _project(db, "P-OTHER")
    await _seed_live_work(db, project.id, other.id)
    await _seed_finished_work(db, project.id)

    work = await SqlAlchemyProjectWork(db).get_live_work(project.id)

    assert work == LIVE_WORK
    assert await SqlAlchemyProjectWork(db).get_live_work(other.id) == ProjectLiveWork(
        bought_demands=1,
    )


async def test_deleting_a_project_with_live_work_answers_409_with_the_counts(
    auth_client, db: AsyncSession
) -> None:
    project = await _project(db, "P-LIVE")
    other = await _project(db, "P-OTHER")
    await _seed_live_work(db, project.id, other.id)
    await _seed_finished_work(db, project.id)
    client = await auth_client(permissions=MANAGER)

    resp = await client.delete(
        f"{PROJECTS}/{project.id}",
        params={"expected_edit_version": await row_version(client, f"{PROJECTS}/{project.id}")},
    )

    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["code"] == "ProjectDeleteBlockedError"
    assert (
        "2 lots, 1 production order, 1 order line, 1 bought item demand, "
        "1 made item demand, 1 source item demand" in body["detail"]
    )
    # Refused as a whole: the project stays and nothing was canceled for it.
    assert (await client.get(f"{PROJECTS}/{project.id}")).status_code == 200
    db.expire_all()
    assert await SqlAlchemyProjectWork(db).get_live_work(project.id) == LIVE_WORK


async def test_a_project_with_only_finished_work_is_deleted(auth_client, db: AsyncSession) -> None:
    project = await _project(db, "P-DONE")
    await _seed_finished_work(db, project.id)
    client = await auth_client(permissions=MANAGER)

    resp = await client.delete(
        f"{PROJECTS}/{project.id}",
        params={"expected_edit_version": await row_version(client, f"{PROJECTS}/{project.id}")},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "archived"


async def test_deleting_a_project_without_live_work_succeeds(auth_client, db: AsyncSession) -> None:
    project = await _project(db, "P-EMPTY")
    client = await auth_client(permissions=MANAGER)

    resp = await client.delete(
        f"{PROJECTS}/{project.id}",
        params={"expected_edit_version": await row_version(client, f"{PROJECTS}/{project.id}")},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "archived"
    assert (await client.get(f"{PROJECTS}/{project.id}")).status_code == 404
