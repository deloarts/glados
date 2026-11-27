"""
The web list endpoints of the bought, made and source item catalogues take
an `ids` filter, with which a catalogue table refetches the rows a live
signal names. Requests go through the real ASGI app, since only that proves
the `Annotated[..., Query()]` binding reads repeated `ids` keys. Rows are
seeded through the ORM models, as in test_api_global_search.py.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
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

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
_COMMON = {"created": NOW, "changed": NOW, "changes": [], "creator_id": 1}


@pytest.fixture
async def reader(auth_client):
    """The first user of a clean-tables test, so id=1, the creator the
    seeded rows name."""
    return await auth_client()


def _bought_item(db, id: int, archived: bool = False) -> None:
    db.add(
        BoughtItemOrmModel(
            **_COMMON,
            id=id,
            archived=archived,
            order_code_1=f"OC-{id}",
            status="active",
            article_name=f"Screw {id}",
            data_source="WEB",
            manufacturer_id=1,
        )
    )


def _made_item(db, id: int, part_number: str | None = None, revision: str = "A") -> None:
    db.add(
        MadeItemOrmModel(
            **_COMMON,
            id=id,
            archived=False,
            revision=revision,
            article_name=f"Bracket {id}",
            status="active",
            data_source="WEB",
            part_number=part_number,
        )
    )


def _source_item(db, id: int) -> None:
    db.add(
        SourceItemOrmModel(
            **_COMMON, id=id, archived=False, type_id=1, material=f"S235-{id}", status="active"
        )
    )


async def _seed(db) -> None:
    db.add(SupplierOrmModel(**_COMMON, id=1, name="Acme", level="B"))
    db.add(SourceItemTypeOrmModel(**_COMMON, id=1, archived=False, name={"enGB": "Sheet"}))
    for item_id in (1, 2, 3):
        _bought_item(db, item_id)
        _made_item(db, item_id)
        _source_item(db, item_id)
    await db.commit()


@pytest.mark.parametrize("path", ["bought-items", "made-items", "source-items"])
async def test_ids_returns_exactly_the_requested_items(reader, db, path):
    await _seed(db)

    body = (await reader.get(f"/api/v1/web/{path}/?ids=1&ids=3")).json()

    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {1, 3}


@pytest.mark.parametrize("path", ["bought-items", "made-items", "source-items"])
async def test_omitted_ids_returns_all(reader, db, path):
    await _seed(db)

    body = (await reader.get(f"/api/v1/web/{path}/")).json()

    assert body["total"] == 3


async def test_ids_keep_the_other_filters(reader, db):
    """An archived row the table's filters hide stays hidden when its id is
    requested, so the live refetch drops it from the table."""
    await _seed(db)
    _bought_item(db, 4, archived=True)
    await db.commit()

    body = (await reader.get("/api/v1/web/bought-items/?ids=1&ids=4")).json()

    assert {item["id"] for item in body["items"]} == {1}


async def test_ids_rank_a_revision_against_its_whole_family(reader, db):
    """With `latest_only`, an old revision whose id is requested still loses
    to the newer revision that was not requested, as it does in the table."""
    await _seed(db)
    _made_item(db, 10, part_number="P-100", revision="A")
    _made_item(db, 11, part_number="P-100", revision="B")
    await db.commit()

    body = (await reader.get("/api/v1/web/made-items/?ids=10&latest_only=true")).json()

    assert body["items"] == []
    assert body["total"] == 0
