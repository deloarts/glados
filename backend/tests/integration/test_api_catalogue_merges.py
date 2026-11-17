"""
Catalogue merges move every reference of the merged-away item to the item
it is merged into before the item is deleted: a made item's demands and
lots, and a bought item's lines, demands and the substitutions that name
it. An item merged into itself is refused as bad input.
"""

import pytest
from sqlalchemy import select

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from tests.integration import _lifecycle_seed as seed


@pytest.fixture(autouse=True)
async def _settings(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_orders(
        AdminOrderSettings(
            id=1,
            order_number_format="ORD-{yy}-{seq:05d}",
            part_number_format="PUR-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await repo.save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()


async def _supplier(client) -> int:
    r = await client.post("/api/v1/web/suppliers/", json={"name": "S", "level": "B"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_an_item_merged_into_itself_is_refused(auth_client) -> None:
    client = await auth_client(
        permissions=["write:bought_items", "write:suppliers", "delete:bought_items"]
    )
    supplier = await _supplier(client)
    item = (
        await client.post(
            "/api/v1/web/bought-items/",
            json={"order_code_1": "SELF", "article_name": "Self", "manufacturer_id": supplier},
        )
    ).json()

    merged = await client.post(
        f"/api/v1/web/bought-items/{item['id']}/merge", json={"target_id": item["id"]}
    )

    assert merged.status_code == 422, merged.text


async def test_a_bought_merge_moves_the_substitutions_that_name_the_item(auth_client, db) -> None:
    client = await auth_client(
        permissions=["write:bought_items", "write:suppliers", "delete:bought_items"]
    )
    supplier = await _supplier(client)
    source = (
        await client.post(
            "/api/v1/web/bought-items/",
            json={"order_code_1": "SRC", "article_name": "Src", "manufacturer_id": supplier},
        )
    ).json()
    target = (
        await client.post(
            "/api/v1/web/bought-items/",
            json={"order_code_1": "TGT", "article_name": "Tgt", "manufacturer_id": supplier},
        )
    ).json()
    order = await seed.order(db, "draft")
    line = await seed.line(db, order, "pending", bought_item_id=source["id"])
    await seed.bought_demand(db, "allocated", line, 5.0, item_id=target["id"])
    allocation = (await db.scalars(select(BoughtItemAllocationOrmModel))).one()
    allocation.substitute_item_id = source["id"]
    allocation.substitute_reason = "equivalent"
    await db.commit()
    await seed.settle(db)

    merged = await client.post(
        f"/api/v1/web/bought-items/{source['id']}/merge", json={"target_id": target["id"]}
    )

    assert merged.status_code == 200, merged.text
    db.expunge_all()
    allocation = (await db.scalars(select(BoughtItemAllocationOrmModel))).one()
    # The line and the demand both name the target now: no substitution left.
    assert (allocation.substitute_item_id, allocation.substitute_reason) == (None, None)
    assert await db.get(BoughtItemOrmModel, source["id"]) is None


async def test_a_made_merge_moves_the_items_demands_and_lots(auth_client, db) -> None:
    client = await auth_client(permissions=["write:made_items", "delete:made_items"])
    source = (
        await client.post("/api/v1/web/made-items/", json={"revision": "A", "article_name": "S"})
    ).json()
    target = (
        await client.post("/api/v1/web/made-items/", json={"revision": "A", "article_name": "T"})
    ).json()
    lot = await seed.lot(db, "draft")
    lot.made_item_id = source["id"]
    demand = await seed.made_demand(db, "allocated", lot, 5.0)
    demand.made_item_id = source["id"]
    await db.commit()
    await seed.settle(db)

    merged = await client.post(
        f"/api/v1/web/made-items/{source['id']}/merge", json={"target_id": target["id"]}
    )

    assert merged.status_code == 200, merged.text
    db.expunge_all()
    moved_demand = await db.get(MadeItemDemandItemOrmModel, demand.id)
    moved_lot = await db.get(ProductionLotOrmModel, lot.id)
    assert moved_demand is not None and moved_lot is not None
    assert (moved_demand.made_item_id, moved_lot.made_item_id) == (target["id"], target["id"])
    assert await db.get(MadeItemOrmModel, source["id"]) is None


@pytest.mark.parametrize("kind", ["source_demand", "lot_source"])
async def test_a_bought_merge_moves_the_raw_material_that_names_the_item(
    auth_client, db, kind
) -> None:
    client = await auth_client(
        permissions=["write:bought_items", "write:suppliers", "delete:bought_items"]
    )
    supplier = await _supplier(client)
    items = []
    for code in ("RAW-SRC", "RAW-TGT"):
        created = await client.post(
            "/api/v1/web/bought-items/",
            json={"order_code_1": code, "article_name": code, "manufacturer_id": supplier},
        )
        assert created.status_code == 201, created.text
        items.append(created.json())
    source, target = items
    if kind == "source_demand":
        lot = await seed.lot(db, "planned")
        demand = await seed.source_demand(db, "open", bought_item_id=source["id"], lot_id=lot.id)
        model, row_id, column = SourceItemDemandItemOrmModel, demand.id, "bought_item_id"
    else:
        lot = await seed.lot(db, "planned", source_bought_item_id=source["id"])
        model, row_id, column = ProductionLotOrmModel, lot.id, "source_bought_item_id"
    await db.commit()
    await seed.settle(db)

    merged = await client.post(
        f"/api/v1/web/bought-items/{source['id']}/merge", json={"target_id": target["id"]}
    )

    assert merged.status_code == 200, merged.text
    db.expunge_all()
    row = await db.get(model, row_id)
    assert row is not None and getattr(row, column) == target["id"]
