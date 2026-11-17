"""
The product detail page rolls up demands, orders and costs over all
projects built on the product. This covers the `product_id` filter on the
three demand lists and the order list, and `GET /products/{id}/summary`.

Every test arranges product A with projects A1 and A2 and product B with
project B1, so a row of B1 is the one that must never show up for A.
Demands and order lines are inserted through the repositories and the ORM
directly; the SQLite test database does not enforce foreign keys, so the
catalogue items they point at need not exist.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from itertools import count

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.project import Project
from tests.integration.test_demand_allocation_filters import _bought_demand as _save_bought
from tests.integration.test_demand_table_filters import _made_demand as _save_made
from tests.integration.test_demand_table_filters import _source_demand as _save_source

NOW = datetime(2026, 8, 6, tzinfo=UTC)
TODAY = date(2026, 8, 6)

_order_item_ids = count(1)


@dataclass
class Arrangement:
    creator_id: int
    product_a: int
    product_b: int
    project_a1: int
    project_a2: int
    project_b1: int


async def _product(db: AsyncSession, creator_id: int, number: str) -> int:
    saved = await SqlAlchemyProductRepository(db).save(
        Product(id=0, created=NOW, product_number=number, creator_id=creator_id)
    )
    await db.commit()
    return saved.id


async def _project(db: AsyncSession, creator_id: int, number: str, product_id: int) -> int:
    saved = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0, created=NOW, project_number=number, product_id=product_id, creator_id=creator_id
        )
    )
    await db.commit()
    return saved.id


async def _arrange(db: AsyncSession, creator_id: int) -> Arrangement:
    product_a = await _product(db, creator_id, "PR-A")
    product_b = await _product(db, creator_id, "PR-B")
    return Arrangement(
        creator_id=creator_id,
        product_a=product_a,
        product_b=product_b,
        project_a1=await _project(db, creator_id, "J-A1", product_a),
        project_a2=await _project(db, creator_id, "J-A2", product_a),
        project_b1=await _project(db, creator_id, "J-B1", product_b),
    )


async def _bought_demand(db: AsyncSession, creator_id: int, project_id: int) -> int:
    demand_id = await _save_bought(db, creator_id, project_id, quantity=1.0)
    await db.commit()
    return demand_id


async def _made_demand(db: AsyncSession, creator_id: int, project_id: int) -> int:
    demand_id = await _save_made(db, creator_id, project_id, made_item_id=1)
    await db.commit()
    return demand_id


async def _source_demand(db: AsyncSession, creator_id: int, project_id: int) -> int:
    demand_id = await _save_source(db, creator_id, project_id)
    await db.commit()
    return demand_id


async def _supplier(db: AsyncSession, creator_id: int, name: str) -> int:
    supplier = SupplierOrmModel(
        name=name, level="A", creator_id=creator_id, created=NOW, changed=NOW
    )
    db.add(supplier)
    await db.commit()
    return supplier.id


async def _order(db: AsyncSession, creator_id: int, supplier_id: int, number: str) -> int:
    order = OrderOrmModel(
        created=TODAY,
        changes=[],
        order_number=number,
        status="draft",
        creator_id=creator_id,
        supplier_id=supplier_id,
    )
    db.add(order)
    await db.commit()
    return order.id


async def _order_item(
    db: AsyncSession,
    *,
    order_id: int,
    supplier_id: int,
    project_id: int,
    creator_id: int,
    price: int,
    quantity: float,
    quantity_delivered: float = 0.0,
) -> None:
    db.add(
        OrderItemOrmModel(
            created=TODAY,
            changes=[],
            status="pending",
            position=next(_order_item_ids),
            quantity=quantity,
            quantity_delivered=quantity_delivered,
            unit="PCS",
            items_per_unit=1.0,
            creator_id=creator_id,
            order_id=order_id,
            supplier_id=supplier_id,
            project_id=project_id,
            bought_item_id=1,
            line_type="BOUGHT",
            price=price,
        )
    )
    await db.commit()


@pytest.fixture
async def arranged(db, create_user) -> Arrangement:
    arranger = await create_user(username="arranger", email="arranger@example.com")
    return await _arrange(db, arranger.id)


@pytest.fixture
async def reader(auth_client):
    return await auth_client()


async def _ids(client, path: str, **params) -> list[int]:
    resp = await client.get(path, params=params)
    assert resp.status_code == 200, resp.text
    return sorted(row["id"] for row in resp.json()["items"])


# ── Demand lists ──────────────────────────────────────────────────────


class TestDemandListsProductFilter:
    async def test_bought_demands_of_the_products_projects(self, db, arranged, reader):
        a1 = await _bought_demand(db, arranged.creator_id, arranged.project_a1)
        a2 = await _bought_demand(db, arranged.creator_id, arranged.project_a2)
        b1 = await _bought_demand(db, arranged.creator_id, arranged.project_b1)
        path = "/api/v1/web/bought-items-demands/"

        assert await _ids(reader, path, product_id=arranged.product_a) == sorted([a1, a2])
        assert await _ids(reader, path, product_id=arranged.product_b) == [b1]

    async def test_deleted_project_is_left_out(self, db, arranged, reader):
        kept = await _bought_demand(db, arranged.creator_id, arranged.project_a1)
        await _bought_demand(db, arranged.creator_id, arranged.project_a2)
        await db.execute(
            update(ProjectOrmModel)
            .where(ProjectOrmModel.id == arranged.project_a2)
            .values(deleted=True)
        )
        await db.commit()
        path = "/api/v1/web/bought-items-demands/"

        assert await _ids(reader, path, product_id=arranged.product_a) == [kept]

    async def test_made_demands_of_the_products_projects(self, db, arranged, reader):
        a1 = await _made_demand(db, arranged.creator_id, arranged.project_a1)
        a2 = await _made_demand(db, arranged.creator_id, arranged.project_a2)
        b1 = await _made_demand(db, arranged.creator_id, arranged.project_b1)
        path = "/api/v1/web/made-items-demands/"

        assert await _ids(reader, path, product_id=arranged.product_a) == sorted([a1, a2])
        assert await _ids(reader, path, product_id=arranged.product_b) == [b1]

    async def test_source_demands_of_the_products_projects(self, db, arranged, reader):
        a1 = await _source_demand(db, arranged.creator_id, arranged.project_a1)
        a2 = await _source_demand(db, arranged.creator_id, arranged.project_a2)
        b1 = await _source_demand(db, arranged.creator_id, arranged.project_b1)
        path = "/api/v1/web/source-item-demands/"

        assert await _ids(reader, path, product_id=arranged.product_a) == sorted([a1, a2])
        assert await _ids(reader, path, product_id=arranged.product_b) == [b1]

    async def test_product_without_projects_matches_nothing(self, db, arranged, reader):
        await _bought_demand(db, arranged.creator_id, arranged.project_a1)
        empty = await _product(db, arranged.creator_id, "PR-EMPTY")

        assert await _ids(reader, "/api/v1/web/bought-items-demands/", product_id=empty) == []


# ── Order list ────────────────────────────────────────────────────────


class TestOrderListProductFilter:
    async def test_orders_with_an_item_for_the_products_projects(self, db, arranged, reader):
        uid = arranged.creator_id
        supplier = await _supplier(db, uid, "Acme")
        order_a1 = await _order(db, uid, supplier, "O-A1")
        order_a2 = await _order(db, uid, supplier, "O-A2")
        order_b1 = await _order(db, uid, supplier, "O-B1")
        # One order carries lines for A1 and B1, so it belongs to both products.
        order_mixed = await _order(db, uid, supplier, "O-MIX")
        for order_id, project_id in [
            (order_a1, arranged.project_a1),
            (order_a2, arranged.project_a2),
            (order_b1, arranged.project_b1),
            (order_mixed, arranged.project_a1),
            (order_mixed, arranged.project_b1),
        ]:
            await _order_item(
                db,
                order_id=order_id,
                supplier_id=supplier,
                project_id=project_id,
                creator_id=uid,
                price=100,
                quantity=1.0,
            )
        path = "/api/v1/web/orders/"

        assert await _ids(reader, path, product_id=arranged.product_a) == sorted(
            [order_a1, order_a2, order_mixed]
        )
        assert await _ids(reader, path, product_id=arranged.product_b) == sorted(
            [order_b1, order_mixed]
        )


# ── Product summary ───────────────────────────────────────────────────


class TestProductSummary:
    async def test_aggregates_the_products_projects_only(
        self, db, arranged, reader, allow_lifecycle_drift
    ):
        """Delivered quantities are stored on the lines directly instead of
        through delivery rows, which the summary does not read, so the
        lifecycle drift check is switched off here."""
        uid = arranged.creator_id
        acme = await _supplier(db, uid, "Acme")
        bolt = await _supplier(db, uid, "Bolt")
        order_acme = await _order(db, uid, acme, "O-ACME")
        order_bolt = await _order(db, uid, bolt, "O-BOLT")
        order_other = await _order(db, uid, acme, "O-OTHER")
        # Acme: one order with lines for both A projects, counted once.
        await _order_item(
            db,
            order_id=order_acme,
            supplier_id=acme,
            project_id=arranged.project_a1,
            creator_id=uid,
            price=100,
            quantity=2.0,
            quantity_delivered=1.0,
        )
        await _order_item(
            db,
            order_id=order_acme,
            supplier_id=acme,
            project_id=arranged.project_a2,
            creator_id=uid,
            price=50,
            quantity=4.0,
            quantity_delivered=4.0,
        )
        await _order_item(
            db,
            order_id=order_bolt,
            supplier_id=bolt,
            project_id=arranged.project_a2,
            creator_id=uid,
            price=10,
            quantity=3.0,
        )
        # Product B's project, must not leak into product A's summary.
        await _order_item(
            db,
            order_id=order_other,
            supplier_id=acme,
            project_id=arranged.project_b1,
            creator_id=uid,
            price=1000,
            quantity=1.0,
            quantity_delivered=1.0,
        )
        await _bought_demand(db, uid, arranged.project_a1)
        await _bought_demand(db, uid, arranged.project_a2)
        await _bought_demand(db, uid, arranged.project_b1)

        resp = await reader.get(f"/api/v1/web/products/{arranged.product_a}/summary")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_ordered_cost"] == 100 * 2 + 50 * 4 + 10 * 3
        assert body["total_delivered_cost"] == 100 * 1 + 50 * 4
        assert body["order_count"] == 2
        assert sorted(body["cost_by_supplier"], key=lambda r: r["supplier_name"]) == [
            {
                "supplier_id": acme,
                "supplier_name": "Acme",
                "ordered_cost": 400,
                "delivered_cost": 300,
            },
            {
                "supplier_id": bolt,
                "supplier_name": "Bolt",
                "ordered_cost": 30,
                "delivered_cost": 0,
            },
        ]
        assert body["demand_counts"] == {"open": 2}

    async def test_project_summary_is_unchanged(self, db, arranged, reader):
        uid = arranged.creator_id
        acme = await _supplier(db, uid, "Acme")
        order = await _order(db, uid, acme, "O-ACME")
        await _order_item(
            db,
            order_id=order,
            supplier_id=acme,
            project_id=arranged.project_a1,
            creator_id=uid,
            price=100,
            quantity=2.0,
        )
        await _order_item(
            db,
            order_id=order,
            supplier_id=acme,
            project_id=arranged.project_a2,
            creator_id=uid,
            price=50,
            quantity=4.0,
        )
        await _bought_demand(db, uid, arranged.project_a1)

        resp = await reader.get(f"/api/v1/web/projects/{arranged.project_a1}/summary")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_ordered_cost"] == 200
        assert body["order_count"] == 1
        assert body["demand_counts"] == {"open": 1}

    async def test_product_without_projects_has_an_empty_summary(self, db, arranged, reader):
        empty = await _product(db, arranged.creator_id, "PR-EMPTY")

        resp = await reader.get(f"/api/v1/web/products/{empty}/summary")

        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "total_ordered_cost": 0,
            "total_delivered_cost": 0,
            "order_count": 0,
            "cost_by_supplier": [],
            "demand_counts": {},
        }

    async def test_unknown_product_is_not_found(self, reader):
        resp = await reader.get("/api/v1/web/products/999999/summary")

        assert resp.status_code == 404
