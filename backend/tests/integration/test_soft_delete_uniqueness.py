"""
Database-level guarantees of the partial unique indexes `uq_*_active`,
each `WHERE archived IS false` (`WHERE deleted IS false` for
project_table, which keeps its `deleted` column).

These assert against the schema itself rather than through the API,
because the property being protected is a *database* invariant that the
application-level uniqueness pre-checks rely on. If a future migration
recreated one of these as a plain UNIQUE, every API-level test would
still pass, the app's own check would keep rejecting duplicates, right
up until someone archived a row and reused its identifier, which would
then fail with an IntegrityError instead of succeeding.

Both halves matter and are tested for each of the four columns: an
archived row must release its value (the point of the change), and two
live rows must still not share one (the relaxation must not overshoot
into no uniqueness at all).

Rows are built by introspecting each table's NOT NULL columns from the ORM
metadata rather than hardcoding a column list, so adding a required column
to any of these models won't silently break this file.

The labeled catalogue tables (article groups, source item types,
fabrication and inspection methods) store their name as a language map,
which a unique index cannot compare per language, so their name rule lives
in the use cases instead. `TestLabeledNameUniqueness` checks the same two
halves for them through the web API.
"""

import httpx
import pytest
from sqlalchemy import Boolean
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import PickleType
from sqlalchemy import String
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.production import (
    AdminProductionSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.domain.value_objects.permission import Permission

CASES = [
    ("customer_table", "vat_id", "uq_customer_vat_id_active"),
    ("supplier_table", "vat_id", "uq_supplier_vat_id_active"),
    ("product_table", "product_number", "uq_product_product_number_active"),
    ("project_table", "project_number", "uq_project_project_number_active"),
    ("bought_item_table", "gtin", "uq_bought_item_gtin_active"),
]
IDS = [c[0] for c in CASES]

# project_table is the one deliberate exception to the rename: every other
# table's soft-delete flag column is `archived`.
_FLAG_COLUMN = {"project_table": "deleted"}


def _flag_column(table: str) -> str:
    return _FLAG_COLUMN.get(table, "archived")


def _placeholder(column):
    """A minimal literal satisfying `column`'s type, for filling required
    columns this test doesn't otherwise care about."""
    t = column.type
    if isinstance(t, Boolean):
        return "0"
    if isinstance(t, Integer | Numeric):
        return "1"
    if isinstance(t, DateTime):
        return "'2026-01-01 00:00:00'"
    if isinstance(t, Date):
        return "'2026-01-01'"
    if isinstance(t, PickleType):
        return "x'80'"
    if isinstance(t, String):
        return "'x'"
    return "'x'"


async def _insert(conn, table: str, col: str, value: str, *, archived: bool, row_id: int) -> None:
    tbl = Base.metadata.tables[table]
    flag_column = _flag_column(table)
    values: dict[str, str] = {}
    for column in tbl.columns:
        if column.name == col:
            values[column.name] = f"'{value}'"
        elif column.name == "id":
            values[column.name] = str(row_id)
        elif column.name == "public_id":
            # Unique per row_id: the generic 'x' placeholder below would
            # collide with public_id's own unique index across the several
            # rows each test inserts into the same table.
            values[column.name] = f"'{row_id:032x}'"
        elif column.name == flag_column:
            values[column.name] = "1" if archived else "0"
        elif not column.nullable and column.server_default is None:
            # Only server_defaults apply to a raw SQL INSERT; a Python-side
            # `default=` never fires here, so those columns still need a value.
            values[column.name] = _placeholder(column)
    columns = ", ".join(values)
    literals = ", ".join(values.values())
    await conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({literals})"))


@pytest.fixture
async def conn(db):
    """Session on the shared engine, with the target tables emptied."""
    for table, *_ in CASES:
        await db.execute(text(f"DELETE FROM {table}"))  # names from CASES
    await db.commit()
    return db


@pytest.mark.parametrize("table,col,index", CASES, ids=IDS)
class TestPartialUniqueIndexes:
    async def test_index_exists_and_is_partial(self, conn, table, col, index):
        row = (
            await conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='index' AND name=:n"), {"n": index}
            )
        ).first()

        assert row is not None, f"{index} is missing, was the migration reverted?"
        assert "UNIQUE" in row[0].upper()
        assert "WHERE" in row[0].upper(), f"{index} is not partial"

    async def test_soft_deleted_row_releases_its_value(self, conn, table, col, index):
        await _insert(conn, table, col, "VAL-1", archived=True, row_id=1)
        await conn.commit()

        await _insert(conn, table, col, "VAL-1", archived=False, row_id=2)
        await conn.commit()

        count = (
            await conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {col}='VAL-1'"))
        ).scalar()
        assert count == 2

    async def test_many_soft_deleted_rows_may_share_a_value(self, conn, table, col, index):
        """Repeated delete/recreate/delete cycles succeed: tombstones
        accumulate without colliding."""
        for i in (1, 2, 3):
            await _insert(conn, table, col, "VAL-1", archived=True, row_id=i)
        await conn.commit()

        count = (
            await conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {col}='VAL-1'"))
        ).scalar()
        assert count == 3

    async def test_two_live_rows_still_cannot_share_a_value(self, conn, table, col, index):
        await _insert(conn, table, col, "VAL-1", archived=False, row_id=1)
        await conn.commit()

        with pytest.raises(IntegrityError):
            await _insert(conn, table, col, "VAL-1", archived=False, row_id=2)
            await conn.commit()
        await conn.rollback()

    async def test_undeleting_into_a_taken_value_is_rejected(self, conn, table, col, index):
        """The index is enforced on UPDATE too, not just INSERT, a
        tombstone cannot be revived onto a now-live value."""
        await _insert(conn, table, col, "VAL-1", archived=True, row_id=1)
        await _insert(conn, table, col, "VAL-1", archived=False, row_id=2)
        await conn.commit()

        flag_column = _flag_column(table)
        with pytest.raises(IntegrityError):
            await conn.execute(text(f"UPDATE {table} SET {flag_column}=0 WHERE id=1"))
            await conn.commit()
        await conn.rollback()

    async def test_distinct_values_are_always_fine(self, conn, table, col, index):
        await _insert(conn, table, col, "VAL-1", archived=False, row_id=1)
        await _insert(conn, table, col, "VAL-2", archived=False, row_id=2)
        await conn.commit()

        count = (await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar()
        assert count == 2


LABELED = [
    ("article-groups", Permission.WRITE_ARTICLE_GROUPS),
    ("source-item-types", Permission.WRITE_SOURCE_ITEM_TYPES),
    ("fabrication-methods", Permission.WRITE_FABRICATION_METHODS),
    ("inspection-methods", Permission.WRITE_INSPECTION_METHODS),
]


@pytest.mark.parametrize("resource,write", LABELED, ids=[resource for resource, _ in LABELED])
class TestLabeledNameUniqueness:
    """The use case rule that replaced the partial unique index on `name`:
    an archived row releases its name, two live rows cannot share one in the
    same language (ignoring case and surrounding whitespace), and restoring
    an archived row onto a name a live row now holds is refused."""

    @pytest.fixture(autouse=True)
    async def _seed_production_settings(self, db) -> None:
        """Archiving an inspection method reads the production settings,
        which the shared conftest does not seed."""
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

    @pytest.fixture
    async def client(self, auth_client, write) -> httpx.AsyncClient:
        client: httpx.AsyncClient = await auth_client(permissions=[write])
        return client

    async def _create(self, client: httpx.AsyncClient, resource: str, name: str) -> httpx.Response:
        return await client.post(f"/api/v1/web/{resource}/", json={"name": {"enGB": name}})

    async def test_archived_row_releases_its_name(self, client, resource, write):
        first = await self._create(client, resource, "VAL-1")
        assert first.status_code == 201, first.text
        archived = await client.post(f"/api/v1/web/{resource}/{first.json()['id']}/archive")
        assert archived.status_code == 200, archived.text

        second = await self._create(client, resource, "VAL-1")
        assert second.status_code == 201, second.text

    async def test_two_live_rows_still_cannot_share_a_name(self, client, resource, write):
        first = await self._create(client, resource, "VAL-1")
        assert first.status_code == 201, first.text

        second = await self._create(client, resource, " val-1 ")
        assert second.status_code == 409, second.text

    async def test_restoring_onto_a_taken_name_is_rejected(self, client, resource, write):
        first = await self._create(client, resource, "VAL-1")
        first_id = first.json()["id"]
        archived = await client.post(f"/api/v1/web/{resource}/{first_id}/archive")
        assert archived.status_code == 200, archived.text
        second = await self._create(client, resource, "VAL-1")
        assert second.status_code == 201, second.text

        restored = await client.post(f"/api/v1/web/{resource}/{first_id}/restore")
        assert restored.status_code == 409, restored.text

    async def test_distinct_names_are_always_fine(self, client, resource, write):
        assert (await self._create(client, resource, "VAL-1")).status_code == 201
        assert (await self._create(client, resource, "VAL-2")).status_code == 201
