"""
GET /api/v1/web/search/ over real HTTP: rows are seeded directly through
the ORM models (mirroring test_order_item_filters.py/test_order_item_naming.py's
approach for the lot -> lot position -> production order chain), not
through the create endpoints, since a search hit needs specific columns
(soft-delete flags, secondary text fields) that aren't all reachable
through every resource's create payload.

Covers which columns are searched per resource, the wire contract (fixed
group order, always-present groups, query validation) and portable SQL
ranking (exact > prefix > contains, ties newest first).
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model import (
    ProductionMachineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
TODAY = date(2026, 8, 26)

# The partial unique index on ProductionOrderOrmModel.
# queue_sequence is scoped per machine/pool/unassigned, and every order
# this file builds is unassigned (machine_id=machine_pool_id=None), so
# they all share one scope and need distinct sequence numbers, the same
# rationale as test_production_order_repository.py's module-global counter.
_queue_sequence = itertools.count(1)

D4_ORDER = [
    "products",
    "projects",
    "bought-items",
    "made-items",
    "source-items",
    "orders",
    "production-lots",
    "production-orders",
    "calculations",
    "checklists",
    "meetings",
]


@pytest.fixture
async def writer(auth_client):
    """The only user created so far in a clean-tables test, so id=1,
    same assumption test_api_projects_pagination.py's TestList makes."""
    return await auth_client()


async def _search(client, q: str, **params):
    return await client.get("/api/v1/web/search/", params={"q": q, **params})


# ── ORM row builders ─────────────────────────────────────────────────


def _product(
    db,
    id: int,
    product_number: str,
    description: str | None = None,
    archived: bool = False,
    customer_id: int | None = None,
):
    db.add(
        ProductOrmModel(
            id=id,
            created=NOW,
            product_number=product_number,
            description=description,
            designated_user_id=1,
            creator_id=1,
            archived=archived,
            customer_id=customer_id,
        )
    )


def _project(
    db,
    id: int,
    project_number: str,
    description: str | None = None,
    deleted: bool = False,
    customer_id: int | None = None,
    product_id: int | None = None,
):
    db.add(
        ProjectOrmModel(
            id=id,
            created=NOW,
            project_number=project_number,
            description=description,
            designated_user_id=1,
            creator_id=1,
            deleted=deleted,
            customer_id=customer_id,
            product_id=product_id,
        )
    )


def _customer(db, id: int, name: str, legal_name: str | None = None, archived: bool = False):
    db.add(
        CustomerOrmModel(
            id=id,
            created=TODAY,
            changes=[],
            name=name,
            legal_name=legal_name,
            level="B",
            creator_id=1,
            archived=archived,
        )
    )


def _bought_item(
    db,
    id: int,
    article_name: str,
    order_code_1: str = "OC-1",
    order_code_2: str | None = None,
    part_number: str | None = None,
    gtin: str | None = None,
    ean: str | None = None,
    note: str | None = None,
    archived: bool = False,
    manufacturer_id: int = 1,
):
    db.add(
        BoughtItemOrmModel(
            id=id,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=archived,
            order_code_1=order_code_1,
            order_code_2=order_code_2,
            gtin=gtin,
            ean=ean,
            status="active",
            article_name=article_name,
            data_source="WEB",
            part_number=part_number,
            note=note,
            creator_id=1,
            manufacturer_id=manufacturer_id,
        )
    )


def _made_item(
    db,
    id: int,
    article_name: str,
    part_number: str | None = None,
    material: str | None = None,
    note: str | None = None,
    archived: bool = False,
):
    db.add(
        MadeItemOrmModel(
            id=id,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=archived,
            revision="A",
            article_name=article_name,
            status="active",
            data_source="WEB",
            part_number=part_number,
            material=material,
            note=note,
            creator_id=1,
        )
    )


def _source_item_type(db, id: int, name: str):
    db.add(
        SourceItemTypeOrmModel(
            id=id,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            name={"enGB": name},
            creator_id=1,
        )
    )


def _source_item(
    db,
    id: int,
    type_id: int,
    material: str,
    order_code_1: str | None = None,
    order_code_2: str | None = None,
    dimension: str | None = None,
    note: str | None = None,
    archived: bool = False,
    manufacturer_id: int | None = None,
):
    db.add(
        SourceItemOrmModel(
            id=id,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=archived,
            type_id=type_id,
            dimension=dimension,
            material=material,
            note=note,
            order_code_1=order_code_1,
            order_code_2=order_code_2,
            creator_id=1,
            manufacturer_id=manufacturer_id,
        )
    )


def _order(
    db,
    id: int,
    order_number: str,
    note: str | None = None,
    storage_place: str | None = None,
    status: str = "draft",
):
    db.add(
        OrderOrmModel(
            id=id,
            order_number=order_number,
            created=NOW,
            changes=[],
            status=status,
            note=note,
            storage_place=storage_place,
            creator_id=1,
            supplier_id=1,
            # The intent a requested order's status stands for.
            requested_at=NOW if status == "requested" else None,
        )
    )


def _production_lot(
    db,
    id: int,
    lot_number: str,
    made_item_id: int,
    project_id: int,
    note: str | None = None,
    status: str = "draft",
    source_item_id: int | None = None,
    source_bought_item_id: int | None = None,
    source_made_item_id: int | None = None,
):
    db.add(
        ProductionLotOrmModel(
            id=id,
            created=NOW,
            changes=[],
            lot_number=lot_number,
            quantity=10.0,
            status=status,
            priority="normal",
            note=note,
            creator_id=1,
            made_item_id=made_item_id,
            project_id=project_id,
            source_item_id=source_item_id,
            source_bought_item_id=source_bought_item_id,
            source_made_item_id=source_made_item_id,
        )
    )


def _lot_position(
    db,
    id: int,
    lot_id: int,
    sequence: int = 1,
    kind: str = "internal",
    status: str = "ordered_or_queued",
):
    """A position its production order makes INTERNAL and queued; one
    without an order passes `kind="unassigned"` and `status="pending"`."""
    db.add(
        LotPositionOrmModel(
            id=id,
            created=NOW,
            changes=[],
            sequence=sequence,
            kind=kind,
            status=status,
            quantity=10.0,
            quantity_completed=0.0,
            creator_id=1,
            lot_id=lot_id,
        )
    )


def _fabrication_method(db, id: int, name: str):
    db.add(
        FabricationMethodOrmModel(
            id=id,
            created=NOW,
            changed=NOW,
            name={"enGB": name},
            creator_id=1,
        )
    )


def _lot_step(
    db, id: int, lot_id: int, position_id: int, fabrication_method_id: int, sequence: int = 1
):
    db.add(
        LotStepOrmModel(
            id=id,
            created=NOW,
            sequence=sequence,
            creator_id=1,
            fabrication_method_id=fabrication_method_id,
            lot_id=lot_id,
            position_id=position_id,
            role="fabrication",
        )
    )


def _production_machine(db, id: int, internal_name: str):
    db.add(
        ProductionMachineOrmModel(
            id=id,
            created=TODAY,
            internal_name=internal_name,
            vendor="Vendor",
            model="Model",
            creator_id=1,
        )
    )


def _supplier(db, id: int, name: str):
    db.add(
        SupplierOrmModel(
            id=id,
            created=NOW,
            changed=NOW,
            changes=[],
            name=name,
            level="B",
            creator_id=1,
        )
    )


def _order_item(
    db,
    id: int,
    order_id: int,
    project_id: int,
    bought_item_id: int | None = None,
    source_item_id: int | None = None,
    lot_position_id: int | None = None,
):
    """The `orders` related-via routes need order_item lines identifying a
    bought item, a source item, or a made-item lot position (mutually
    exclusive per ck_order_item_line_type, inferred here from whichever id
    is passed) and/or a project: project_id is independent of that
    exclusivity, so a line can carry it alongside any of the three."""
    if bought_item_id is not None:
        line_type = "BOUGHT"
    elif source_item_id is not None:
        line_type = "SOURCE"
    elif lot_position_id is not None:
        line_type = "MADE"
    else:
        raise ValueError("one of bought_item_id/source_item_id/lot_position_id is required")
    db.add(
        OrderItemOrmModel(
            id=id,
            created=NOW,
            changes=[],
            status="pending",
            quantity=1.0,
            quantity_delivered=0.0,
            unit="pcs",
            items_per_unit=1.0,
            creator_id=1,
            order_id=order_id,
            supplier_id=1,
            line_type=line_type,
            bought_item_id=bought_item_id,
            source_item_id=source_item_id,
            lot_position_id=lot_position_id,
            project_id=project_id,
        )
    )


def _source_item_demand_item(
    db,
    id: int,
    lot_id: int,
    project_id: int,
    source_item_id: int | None = None,
    bought_item_id: int | None = None,
):
    db.add(
        SourceItemDemandItemOrmModel(
            id=id,
            created=TODAY,
            changes=[],
            status="open",
            quantity=1.0,
            unit="pcs",
            items_per_unit=1.0,
            creator_id=1,
            lot_id=lot_id,
            project_id=project_id,
            source_item_id=source_item_id,
            bought_item_id=bought_item_id,
        )
    )


def _production_order(
    db,
    id: int,
    production_order_number: str,
    lot_position_id: int,
    note: str | None = None,
    status: str = "queued",
    machine_id: int | None = None,
):
    db.add(
        ProductionOrderOrmModel(
            id=id,
            created=NOW,
            changes=[],
            production_order_number=production_order_number,
            status=status,
            priority="normal",
            pinned=False,
            queue_sequence=next(_queue_sequence),
            quantity=1.0,
            quantity_completed=0.0,
            estimated_duration_minutes=0,
            note=note,
            creator_id=1,
            lot_position_id=lot_position_id,
            machine_id=machine_id,
        )
    )


async def _production_order_chain(
    db,
    id: int,
    production_order_number: str,
    made_item_id: int,
    project_id: int,
    lot_number: str | None = None,
    note: str | None = None,
):
    """A production order needs a lot and a lot position to hang off of,
    same chain test_production_order_repository.py builds, here via direct
    ORM construction instead of the repository layer."""
    _production_lot(
        db,
        id,
        lot_number or f"LOT-{id}",
        made_item_id=made_item_id,
        project_id=project_id,
        status="planned",
    )
    _lot_position(db, id, lot_id=id)
    _production_order(db, id, production_order_number, lot_position_id=id, note=note)
    await db.commit()


# ── Auth / validation ────────────────────────────────────────────────


async def test_requires_authentication(client):
    response = await _search(client, "anything")

    assert response.status_code == 401


async def test_a_query_over_the_max_length_is_rejected(writer):
    response = await _search(writer, "a" * 201)

    assert response.status_code == 422


async def test_a_zero_limit_is_rejected(writer):
    response = await _search(writer, "anything", limit=0)

    assert response.status_code == 422


# ── Wire contract ────────────────────────────────────────────────────


async def test_all_eight_groups_are_present_in_order_on_a_no_hit_query(writer):
    body = (await _search(writer, "no-such-term-anywhere")).json()

    assert body["query"] == "no-such-term-anywhere"
    assert [g["resource"] for g in body["groups"]] == D4_ORDER
    assert all(g["total"] == 0 and g["items"] == [] for g in body["groups"])


async def test_whitespace_only_query_returns_all_empty_groups(writer, db):
    _project(db, 1, "AX-2201")
    await db.commit()

    body = (await _search(writer, "   ")).json()

    assert body["query"] == ""
    assert all(g["total"] == 0 and g["items"] == [] for g in body["groups"])


# ── Ranking: exact > prefix > contains, case-insensitive ──────────────


class TestRanking:
    async def test_exact_beats_prefix_beats_contains(self, writer, db):
        _project(db, 1, "ZZ-AX-22")  # contains only
        _project(db, 2, "AX-220")  # starts with
        _project(db, 3, "AX-22")  # exact
        await db.commit()

        body = (await _search(writer, "ax-22")).json()  # lower-case: also proves case-insensitivity

        group = next(g for g in body["groups"] if g["resource"] == "projects")
        assert group["total"] == 3
        assert [i["label"] for i in group["items"]] == ["AX-22", "AX-220", "ZZ-AX-22"]

    async def test_ties_are_newest_first(self, writer, db):
        _project(db, 1, "TIE-A")
        _project(db, 2, "TIE-B")
        await db.commit()

        body = (await _search(writer, "tie-")).json()

        group = next(g for g in body["groups"] if g["resource"] == "projects")
        assert [i["label"] for i in group["items"]] == ["TIE-B", "TIE-A"]


# ── Secondary columns ────────────────────────────────────────────────


async def test_order_note_is_searched(writer, db):
    _order(db, 1, "O-0001", note="urgent rework needed")
    _order(db, 2, "O-0002", note=None)
    await db.commit()

    body = (await _search(writer, "rework")).json()

    group = next(g for g in body["groups"] if g["resource"] == "orders")
    assert group["total"] == 1
    assert group["items"][0]["label"] == "O-0001"


async def test_source_item_type_name_is_searched(writer, db):
    _source_item_type(db, 1, "Rolled Bar")
    _source_item_type(db, 2, "Sheet Metal")
    _source_item(db, 1, type_id=1, material="1.0037", dimension="40x40x4")
    _source_item(db, 2, type_id=2, material="1.4301", dimension="2x1000x2000")
    await db.commit()

    body = (await _search(writer, "rolled")).json()

    group = next(g for g in body["groups"] if g["resource"] == "source-items")
    assert group["total"] == 1
    assert group["items"][0]["label"] == "1.0037"


# ── Soft delete exclusion ────────────────────────────────────────────


class TestSoftDeleteExclusion:
    async def test_deleted_product_is_excluded(self, writer, db):
        _product(db, 1, "SDEL-PROD-LIVE")
        _product(db, 2, "SDEL-PROD-GONE", archived=True)
        await db.commit()

        body = (await _search(writer, "sdel-prod")).json()

        group = next(g for g in body["groups"] if g["resource"] == "products")
        assert group["total"] == 1
        assert group["items"][0]["label"] == "SDEL-PROD-LIVE"

    async def test_deleted_project_is_excluded(self, writer, db):
        _project(db, 1, "SDEL-PROJ-LIVE")
        _project(db, 2, "SDEL-PROJ-GONE", deleted=True)
        await db.commit()

        body = (await _search(writer, "sdel-proj")).json()

        group = next(g for g in body["groups"] if g["resource"] == "projects")
        assert group["total"] == 1
        assert group["items"][0]["label"] == "SDEL-PROJ-LIVE"

    async def test_deleted_bought_item_is_excluded(self, writer, db):
        _bought_item(db, 1, "SDEL-BOUGHT-LIVE")
        _bought_item(db, 2, "SDEL-BOUGHT-GONE", archived=True)
        await db.commit()

        body = (await _search(writer, "sdel-bought")).json()

        group = next(g for g in body["groups"] if g["resource"] == "bought-items")
        assert group["total"] == 1
        assert group["items"][0]["label"] == "SDEL-BOUGHT-LIVE"

    async def test_deleted_made_item_is_excluded(self, writer, db):
        _made_item(db, 1, "SDEL-MADE-LIVE")
        _made_item(db, 2, "SDEL-MADE-GONE", archived=True)
        await db.commit()

        body = (await _search(writer, "sdel-made")).json()

        group = next(g for g in body["groups"] if g["resource"] == "made-items")
        assert group["total"] == 1
        assert group["items"][0]["label"] == "SDEL-MADE-LIVE"

    async def test_deleted_source_item_is_excluded(self, writer, db):
        _source_item_type(db, 1, "Type-A")
        _source_item(db, 1, type_id=1, material="SDEL-SOURCE-LIVE")
        _source_item(db, 2, type_id=1, material="SDEL-SOURCE-GONE", archived=True)
        await db.commit()

        body = (await _search(writer, "sdel-source")).json()

        group = next(g for g in body["groups"] if g["resource"] == "source-items")
        assert group["total"] == 1
        assert group["items"][0]["label"] == "SDEL-SOURCE-LIVE"


# ── LIKE-metacharacter escaping ──────────────────────────────────────


async def test_percent_and_underscore_are_matched_literally(writer, db):
    _project(db, 1, "50%OFF")  # the literal term should match this...
    _project(db, 2, "50XOFFY")  # ...but not this (would match if % were a wildcard)
    _project(db, 3, "AB_CD")
    _project(db, 4, "ABXCDY")  # would match "AB_CD" search if _ were a wildcard
    await db.commit()

    percent_body = (await _search(writer, "50%")).json()
    percent_group = next(g for g in percent_body["groups"] if g["resource"] == "projects")
    assert percent_group["total"] == 1
    assert percent_group["items"][0]["label"] == "50%OFF"

    underscore_body = (await _search(writer, "ab_cd")).json()
    underscore_group = next(g for g in underscore_body["groups"] if g["resource"] == "projects")
    assert underscore_group["total"] == 1
    assert underscore_group["items"][0]["label"] == "AB_CD"


# ── limit vs total ───────────────────────────────────────────────────


async def test_limit_caps_items_but_total_counts_every_match(writer, db):
    for i in range(1, 8):
        _bought_item(db, i, f"LIMIT-CASE-{i}", order_code_1=f"OC-{i}")
    await db.commit()

    body = (await _search(writer, "limit-case", limit=3)).json()

    group = next(g for g in body["groups"] if g["resource"] == "bought-items")
    assert group["total"] == 7
    assert len(group["items"]) == 3


# ── At least one hit per resource (order coverage) ────────────────────


async def test_every_resource_type_can_produce_a_hit(writer, db):
    _product(db, 1, "ALLHIT-PRODUCT")
    _project(db, 1, "ALLHIT-PROJECT")
    _bought_item(db, 1, "ALLHIT-BOUGHT")
    _made_item(db, 1, "ALLHIT-MADE")
    _source_item_type(db, 1, "Generic")
    _source_item(db, 1, type_id=1, material="ALLHIT-SOURCE")
    _order(db, 1, "ALLHIT-ORDER")
    await db.commit()
    await _production_order_chain(
        db,
        1,
        "ALLHIT-PRODORDER",
        made_item_id=1,
        project_id=1,
        lot_number="ALLHIT-LOT",
    )

    body = (await _search(writer, "allhit")).json()

    totals = {g["resource"]: g["total"] for g in body["groups"]}
    assert totals == {
        "products": 1,
        "projects": 1,
        "bought-items": 1,
        "made-items": 1,
        "source-items": 1,
        "orders": 1,
        "production-lots": 1,
        "production-orders": 1,
        "calculations": 0,
        "checklists": 0,
        "meetings": 0,
    }


# ── rich result details ─────────────────────────────────────────


async def test_bought_item_hit_carries_details(writer, db):
    _bought_item(db, 1, "DETAIL-BOUGHT", order_code_1="OC-DETAIL", part_number="PN-DETAIL")
    await db.commit()

    body = (await _search(writer, "detail-bought")).json()

    group = next(g for g in body["groups"] if g["resource"] == "bought-items")
    details = group["items"][0]["details"]
    assert details["article_name"] == "DETAIL-BOUGHT"
    assert details["part_number"] == "PN-DETAIL"
    assert details["order_code_1"] == "OC-DETAIL"


async def test_made_item_hit_carries_details(writer, db):
    _made_item(db, 1, "DETAIL-MADE", part_number="PN-DETAIL-MADE")
    await db.commit()

    body = (await _search(writer, "detail-made")).json()

    group = next(g for g in body["groups"] if g["resource"] == "made-items")
    details = group["items"][0]["details"]
    assert details["article_name"] == "DETAIL-MADE"
    assert details["part_number"] == "PN-DETAIL-MADE"
    assert details["revision"] == "A"


async def test_order_hit_carries_status_supplier_name_and_item_count(writer, db):
    _supplier(db, 1, "ACME")
    _bought_item(db, 1, "DETAIL-ORDER-ITEM")
    _order(db, 1, "DETAIL-ORDER", status="requested")
    await db.commit()
    _project(db, 99, "LINE-OWNER-PROJECT")
    _order_item(db, 1, order_id=1, bought_item_id=1, project_id=99)
    _order_item(db, 2, order_id=1, bought_item_id=1, project_id=99)
    await db.commit()

    body = (await _search(writer, "detail-order")).json()

    group = next(g for g in body["groups"] if g["resource"] == "orders")
    details = group["items"][0]["details"]
    assert details["status"] == "requested"
    assert details["supplier_name"] == "ACME"
    assert details["item_count"] == 2


async def test_lot_hit_carries_status_made_item_and_source_label_with_a_source(writer, db):
    _made_item(db, 1, "DETAIL-LOT-MADE", part_number="PN-LOT-MADE")
    _project(db, 1, "DETAIL-LOT-PROJECT")
    _source_item_type(db, 1, "Type-Detail")
    _source_item(db, 1, type_id=1, material="1.4301", dimension="Ø40")
    _production_lot(
        db,
        1,
        "DETAIL-LOT-WITH-SOURCE",
        made_item_id=1,
        project_id=1,
        status="draft",
        source_item_id=1,
    )
    await db.commit()

    body = (await _search(writer, "detail-lot-with-source")).json()

    group = next(g for g in body["groups"] if g["resource"] == "production-lots")
    details = group["items"][0]["details"]
    assert details["status"] == "draft"
    assert details["made_item_id"] == 1
    assert details["made_item_part_number"] == "PN-LOT-MADE"
    assert details["made_item_revision"] == "A"
    assert details["made_item_article_name"] == "DETAIL-LOT-MADE"
    assert details["source_label"] == "Ø40 1.4301"


async def test_lot_hit_source_label_is_null_without_a_source(writer, db):
    _made_item(db, 1, "DETAIL-LOT-MADE-2")
    _project(db, 1, "DETAIL-LOT-PROJECT-2")
    _production_lot(db, 1, "DETAIL-LOT-NO-SOURCE", made_item_id=1, project_id=1)
    await db.commit()

    body = (await _search(writer, "detail-lot-no-source")).json()

    group = next(g for g in body["groups"] if g["resource"] == "production-lots")
    assert group["items"][0]["details"]["source_label"] is None


async def test_lot_hit_steps_are_in_position_then_step_sequence_order(writer, db):
    _made_item(db, 1, "DETAIL-LOT-STEPS-MADE")
    _project(db, 1, "DETAIL-LOT-STEPS-PROJECT")
    _production_lot(db, 1, "DETAIL-LOT-STEPS", made_item_id=1, project_id=1)
    _fabrication_method(db, 1, "Sawing")
    _fabrication_method(db, 2, "Milling")
    await db.commit()
    _lot_position(db, 10, lot_id=1, sequence=1, kind="unassigned", status="pending")
    _lot_position(db, 11, lot_id=1, sequence=2, kind="unassigned", status="pending")
    await db.commit()
    _lot_step(db, 100, lot_id=1, position_id=10, fabrication_method_id=1, sequence=1)
    _lot_step(db, 101, lot_id=1, position_id=11, fabrication_method_id=2, sequence=2)
    await db.commit()

    body = (await _search(writer, "detail-lot-steps")).json()

    group = next(g for g in body["groups"] if g["resource"] == "production-lots")
    assert group["items"][0]["details"]["steps"] == ["Sawing", "Milling"]


async def test_production_order_hit_carries_manual_execution_when_unassigned(writer, db):
    _made_item(db, 1, "DETAIL-PRODORDER-MADE")
    _project(db, 1, "DETAIL-PRODORDER-PROJECT")
    await db.commit()
    await _production_order_chain(
        db,
        1,
        "DETAIL-PRODORDER-MANUAL",
        made_item_id=1,
        project_id=1,
    )

    body = (await _search(writer, "detail-prodorder-manual")).json()

    group = next(g for g in body["groups"] if g["resource"] == "production-orders")
    details = group["items"][0]["details"]
    assert details["execution_kind"] == "manual"
    assert details["execution_label"] is None
    assert details["made_item_id"] == 1
    assert details["made_item_article_name"] == "DETAIL-PRODORDER-MADE"


async def test_production_order_hit_carries_machine_execution_when_assigned(writer, db):
    _made_item(db, 1, "DETAIL-PRODORDER-MADE-2")
    _project(db, 1, "DETAIL-PRODORDER-PROJECT-2")
    _production_machine(db, 1, "DMU 50")
    await db.commit()
    _production_lot(db, 1, "DETAIL-PRODORDER-LOT", made_item_id=1, project_id=1, status="planned")
    _lot_position(db, 1, lot_id=1)
    await db.commit()
    _production_order(
        db,
        1,
        "DETAIL-PRODORDER-MACHINE",
        lot_position_id=1,
        machine_id=1,
    )
    await db.commit()

    body = (await _search(writer, "detail-prodorder-machine")).json()

    group = next(g for g in body["groups"] if g["resource"] == "production-orders")
    details = group["items"][0]["details"]
    assert details["execution_kind"] == "machine"
    assert details["execution_label"] == "DMU 50"


# ── match_kind on the three ranking tiers ─────────────────────────


async def test_match_kind_is_exact_prefix_or_contains_for_the_three_ranking_tiers(writer, db):
    _project(db, 1, "ZZ-MK-22")  # contains only
    _project(db, 2, "MK-220")  # starts with
    _project(db, 3, "MK-22")  # exact
    await db.commit()

    body = (await _search(writer, "mk-22")).json()

    group = next(g for g in body["groups"] if g["resource"] == "projects")
    kinds = {item["label"]: item["match_kind"] for item in group["items"]}
    assert kinds == {"MK-22": "exact", "MK-220": "prefix", "ZZ-MK-22": "contains"}


# ── related matches (tier 3) and via_kind ─────────────────────────


class TestRelatedMatches:
    async def test_lot_is_related_via_its_made_items_part_number(self, writer, db):
        _made_item(db, 1, "REL-MADE-ITEM", part_number="REL-PART-99")
        _project(db, 1, "REL-MADE-PROJECT")
        _production_lot(db, 1, "LOT-VIA-MADE", made_item_id=1, project_id=1)
        await db.commit()

        body = (await _search(writer, "rel-part-99")).json()

        group = next(g for g in body["groups"] if g["resource"] == "production-lots")
        assert group["total"] == 1
        item = group["items"][0]
        assert item["label"] == "LOT-VIA-MADE"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "item"

    async def test_lot_is_related_via_a_demand_linked_source_item(self, writer, db):
        _made_item(db, 1, "REL-DEMAND-MADE")
        _project(db, 1, "REL-DEMAND-PROJECT")
        _production_lot(db, 1, "LOT-VIA-DEMAND", made_item_id=1, project_id=1)
        _source_item_type(db, 1, "Type-Demand")
        _source_item(db, 1, type_id=1, material="REL-DEMAND-SOURCE")
        await db.commit()
        _source_item_demand_item(db, 1, lot_id=1, project_id=1, source_item_id=1)
        await db.commit()

        body = (await _search(writer, "rel-demand-source")).json()

        group = next(g for g in body["groups"] if g["resource"] == "production-lots")
        assert group["total"] == 1
        item = group["items"][0]
        assert item["label"] == "LOT-VIA-DEMAND"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "item"

    async def test_lot_is_related_via_its_projects_number(self, writer, db):
        _made_item(db, 1, "REL-PROJNUM-MADE")
        _project(db, 1, "REL-PROJNUM-77")
        _production_lot(db, 1, "LOT-VIA-PROJECT", made_item_id=1, project_id=1)
        await db.commit()

        body = (await _search(writer, "rel-projnum-77")).json()

        group = next(g for g in body["groups"] if g["resource"] == "production-lots")
        item = group["items"][0]
        assert item["label"] == "LOT-VIA-PROJECT"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "project"

    async def test_lot_is_related_via_its_projects_customer(self, writer, db):
        _customer(db, 1, "REL-LOT-CUSTOMER")
        _made_item(db, 1, "REL-CUST-MADE")
        _project(db, 1, "REL-CUST-PROJECT", customer_id=1)
        _production_lot(db, 1, "LOT-VIA-CUSTOMER", made_item_id=1, project_id=1)
        await db.commit()

        body = (await _search(writer, "rel-lot-customer")).json()

        group = next(g for g in body["groups"] if g["resource"] == "production-lots")
        item = group["items"][0]
        assert item["label"] == "LOT-VIA-CUSTOMER"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "customer"

    async def test_lot_is_related_via_its_projects_product(self, writer, db):
        _product(db, 1, "REL-LOT-PRODUCT")
        _made_item(db, 1, "REL-PROD-MADE")
        _project(db, 1, "REL-PROD-PROJECT", product_id=1)
        _production_lot(db, 1, "LOT-VIA-PRODUCT", made_item_id=1, project_id=1)
        await db.commit()

        body = (await _search(writer, "rel-lot-product")).json()

        group = next(g for g in body["groups"] if g["resource"] == "production-lots")
        item = group["items"][0]
        assert item["label"] == "LOT-VIA-PRODUCT"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "product"

    async def test_order_is_related_via_its_bought_item_line(self, writer, db):
        _bought_item(db, 1, "REL-ORDER-BOUGHT")
        _order(db, 1, "ORD-VIA-BOUGHT")
        await db.commit()
        _project(db, 99, "LINE-OWNER-PROJECT")
        _order_item(db, 1, order_id=1, bought_item_id=1, project_id=99)
        await db.commit()

        body = (await _search(writer, "rel-order-bought")).json()

        group = next(g for g in body["groups"] if g["resource"] == "orders")
        item = group["items"][0]
        assert item["label"] == "ORD-VIA-BOUGHT"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "item"

    async def test_order_is_related_via_its_suppliers_name(self, writer, db):
        _supplier(db, 1, "REL-ORDER-SUPPLIER")  # _order() hardcodes supplier_id=1
        _order(db, 1, "ORD-VIA-SUPPLIER")
        await db.commit()

        body = (await _search(writer, "rel-order-supplier")).json()

        group = next(g for g in body["groups"] if g["resource"] == "orders")
        item = group["items"][0]
        assert item["label"] == "ORD-VIA-SUPPLIER"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "supplier"

    async def test_order_is_related_via_its_lines_project(self, writer, db):
        _bought_item(db, 1, "UNRELATED-BOUGHT-ITEM")
        _project(db, 1, "REL-ORDER-PROJECT")
        _order(db, 1, "ORD-VIA-PROJECT")
        await db.commit()
        _order_item(db, 1, order_id=1, bought_item_id=1, project_id=1)
        await db.commit()

        body = (await _search(writer, "rel-order-project")).json()

        group = next(g for g in body["groups"] if g["resource"] == "orders")
        item = group["items"][0]
        assert item["label"] == "ORD-VIA-PROJECT"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "project"

    async def test_production_order_is_related_via_its_lots_own_number(self, writer, db):
        _made_item(db, 1, "REL-PRODORDER-LOT-MADE")
        _project(db, 1, "REL-PRODORDER-LOT-PROJECT")
        _production_lot(
            db, 1, "REL-PRODORDER-LOTNUM", made_item_id=1, project_id=1, status="planned"
        )
        _lot_position(db, 1, lot_id=1)
        await db.commit()
        _production_order(db, 1, "PO-VIA-LOTNUM", lot_position_id=1)
        await db.commit()

        body = (await _search(writer, "rel-prodorder-lotnum")).json()

        group = next(g for g in body["groups"] if g["resource"] == "production-orders")
        item = group["items"][0]
        assert item["label"] == "PO-VIA-LOTNUM"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "lot"

    async def test_production_order_is_related_via_its_lots_made_item(self, writer, db):
        _made_item(db, 1, "REL-PRODORDER-MADE-ITEM", part_number="REL-PRODORDER-PART")
        _project(db, 1, "REL-PRODORDER-MADE-PROJECT")
        _production_lot(db, 1, "PO-MADE-LOT", made_item_id=1, project_id=1, status="planned")
        _lot_position(db, 1, lot_id=1)
        await db.commit()
        _production_order(db, 1, "PO-VIA-MADE-ITEM", lot_position_id=1)
        await db.commit()

        body = (await _search(writer, "rel-prodorder-part")).json()

        group = next(g for g in body["groups"] if g["resource"] == "production-orders")
        item = group["items"][0]
        assert item["label"] == "PO-VIA-MADE-ITEM"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "item"

    async def test_project_is_related_via_its_customer(self, writer, db):
        _customer(db, 1, "REL-PROJECT-CUSTOMER")
        _project(db, 1, "PROJ-VIA-CUSTOMER", customer_id=1)
        await db.commit()

        body = (await _search(writer, "rel-project-customer")).json()

        group = next(g for g in body["groups"] if g["resource"] == "projects")
        item = group["items"][0]
        assert item["label"] == "PROJ-VIA-CUSTOMER"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "customer"

    async def test_project_is_related_via_its_product(self, writer, db):
        _product(db, 1, "REL-PROJECT-PRODUCT")
        _project(db, 1, "PROJ-VIA-PRODUCT", product_id=1)
        await db.commit()

        body = (await _search(writer, "rel-project-product")).json()

        group = next(g for g in body["groups"] if g["resource"] == "projects")
        item = group["items"][0]
        assert item["label"] == "PROJ-VIA-PRODUCT"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "product"

    async def test_product_is_related_via_its_customer(self, writer, db):
        _customer(db, 1, "REL-PRODUCT-CUSTOMER")
        _product(db, 1, "PRODUCT-VIA-CUSTOMER", customer_id=1)
        await db.commit()

        body = (await _search(writer, "rel-product-customer")).json()

        group = next(g for g in body["groups"] if g["resource"] == "products")
        item = group["items"][0]
        assert item["label"] == "PRODUCT-VIA-CUSTOMER"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "customer"

    async def test_bought_item_is_related_via_its_manufacturer(self, writer, db):
        _supplier(db, 1, "REL-BOUGHT-MANUFACTURER")
        _bought_item(db, 1, "BOUGHT-VIA-MANUFACTURER", manufacturer_id=1)
        await db.commit()

        body = (await _search(writer, "rel-bought-manufacturer")).json()

        group = next(g for g in body["groups"] if g["resource"] == "bought-items")
        item = group["items"][0]
        assert item["label"] == "BOUGHT-VIA-MANUFACTURER"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "supplier"

    async def test_source_item_is_related_via_its_manufacturer(self, writer, db):
        _supplier(db, 1, "REL-SOURCE-MANUFACTURER")
        _source_item_type(db, 1, "Type-Rel-Source")
        _source_item(db, 1, type_id=1, material="REL-SOURCE-MATERIAL", manufacturer_id=1)
        await db.commit()

        body = (await _search(writer, "rel-source-manufacturer")).json()

        group = next(g for g in body["groups"] if g["resource"] == "source-items")
        item = group["items"][0]
        assert item["label"] == "REL-SOURCE-MATERIAL"
        assert item["match_kind"] == "related"
        assert item["via_kind"] == "supplier"

    async def test_related_rows_rank_below_an_own_identifier_match_and_total_counts_them(
        self, writer, db
    ):
        _bought_item(db, 1, "RANKTEST-BOUGHT-ITEM")
        _order(db, 1, "RANKTEST-OWN")
        _order(db, 2, "OTHER-999")
        await db.commit()
        _project(db, 99, "LINE-OWNER-PROJECT")
        _order_item(db, 1, order_id=2, bought_item_id=1, project_id=99)
        await db.commit()

        body = (await _search(writer, "ranktest")).json()

        group = next(g for g in body["groups"] if g["resource"] == "orders")
        assert group["total"] == 2
        assert [i["label"] for i in group["items"]] == ["RANKTEST-OWN", "OTHER-999"]
        assert group["items"][0]["match_kind"] != "related"
        assert group["items"][1]["match_kind"] == "related"


# ── fuzzy fallback ─────────────────────────────────────────────────


class TestFuzzyFallback:
    async def test_a_typo_finds_the_row_via_fuzzy_when_strict_finds_nothing(self, writer, db):
        _project(db, 1, "TN-26-00004")
        await db.commit()

        # One digit short of the seeded project_number, not a contiguous
        # substring of it, so the strict ILIKE tiers find nothing.
        body = (await _search(writer, "TN-26-0004")).json()

        group = next(g for g in body["groups"] if g["resource"] == "projects")
        assert group["total"] == 0
        assert len(group["items"]) == 1
        assert group["items"][0]["label"] == "TN-26-00004"
        assert group["items"][0]["match_kind"] == "fuzzy"

    async def test_fuzzy_rows_never_appear_once_strict_already_fills_the_limit(self, writer, db):
        _project(db, 1, "FUZZYCAP-EXACT")
        _project(db, 2, "FUZZYCAP-TYPO-TARGET")
        await db.commit()

        body = (await _search(writer, "fuzzycap-exact", limit=1)).json()

        group = next(g for g in body["groups"] if g["resource"] == "projects")
        assert len(group["items"]) == 1
        assert group["items"][0]["label"] == "FUZZYCAP-EXACT"
        assert group["items"][0]["match_kind"] != "fuzzy"

    async def test_total_excludes_fuzzy_hits(self, writer, db):
        _project(db, 1, "ONLYFUZZY-00004")
        await db.commit()

        body = (await _search(writer, "ONLYFUZZY-0004")).json()

        group = next(g for g in body["groups"] if g["resource"] == "projects")
        assert group["total"] == 0
        assert len(group["items"]) == 1
        assert group["items"][0]["match_kind"] == "fuzzy"


async def test_document_hits_by_number_and_title_leave_personal_ones_out(auth_client, db):
    writer = await auth_client(permissions=[Permission.WRITE_CALCULATIONS])
    calculation = (
        await writer.post(
            "/api/v1/web/calculations",
            json={
                "tool": "drive_sizing",
                "title": "Lift axis DOCSEARCH",
                "inputs": {},
                "results": {},
                "input_version": 1,
                "engine_version": 1,
            },
        )
    ).json()
    _project(db, 7, "DOCSEARCH-P")
    await db.commit()
    shared = (
        await writer.post(
            "/api/v1/web/calculations",
            json={
                "tool": "drive_sizing",
                "title": "Shared DOCSEARCH",
                "inputs": {},
                "results": {},
                "input_version": 1,
                "engine_version": 1,
                "project_id": 7,
            },
        )
    ).json()

    by_title = (await _search(writer, "docsearch")).json()
    group = next(g for g in by_title["groups"] if g["resource"] == "calculations")
    assert [hit["id"] for hit in group["items"]] == [shared["id"]]
    assert calculation["id"] not in [hit["id"] for hit in group["items"]]

    by_number = (await _search(writer, shared["document_number"])).json()
    hit = next(g for g in by_number["groups"] if g["resource"] == "calculations")["items"][0]
    assert (hit["label"], hit["subtitle"], hit["match_kind"]) == (
        shared["document_number"],
        "Shared DOCSEARCH",
        "exact",
    )
    assert hit["details"]["revision"] == shared["revision"]
