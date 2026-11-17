"""
The statement helpers in src/modules/platform/adapters/outbound/persistence/statements.py
and load_user from the user repository, rendered for Postgres so the FOR
UPDATE clause shows. fetch_page and load_by_ids run against a fake session
that records what it is asked to execute.
"""

from typing import Any

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import selectinload

# Loads every model, so the mappers that name each other by string configure.
import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.machine_pool_model import (
    MachinePoolOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model import (
    ProductionMachineOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import load_by_ids
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_load_options
from src.modules.platform.const import DEFAULT_PAGE_SIZE


def _sql(statement: Any) -> str:
    compiled = statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    return " ".join(str(compiled).split())


class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _RecordingSession:
    """Answers every count with `total` and every row read with `rows`."""

    def __init__(self, total: int, rows: list[Any]) -> None:
        self.total = total
        self.rows = rows
        self.statements: list[Any] = []

    async def scalar(self, statement: Any) -> int:
        self.statements.append(statement)
        return self.total

    async def scalars(self, statement: Any) -> _Rows:
        self.statements.append(statement)
        return _Rows(self.rows)


class TestOrderTerm:
    @pytest.mark.parametrize(
        ("order_dir", "expected"), [(None, "ASC"), ("asc", "ASC"), ("x", "ASC"), ("desc", "DESC")]
    )
    def test_order_term_ascending_default_flips_only_on_desc(
        self, order_dir: str | None, expected: str
    ) -> None:
        term = order_term(CustomerOrmModel.name, order_dir, default="asc")
        assert _sql(term) == f"customer_table.name {expected}"

    @pytest.mark.parametrize(
        ("order_dir", "expected"),
        [(None, "DESC"), ("desc", "DESC"), ("ASC", "DESC"), ("asc", "ASC")],
    )
    def test_order_term_descending_default_flips_only_on_asc(
        self, order_dir: str | None, expected: str
    ) -> None:
        term = order_term(CustomerOrmModel.name, order_dir, default="desc")
        assert _sql(term) == f"customer_table.name {expected}"


class TestById:
    def test_by_id_selects_one_primary_key(self) -> None:
        statement = by_id(CustomerOrmModel, 7)

        assert _sql(statement).endswith("FROM customer_table WHERE customer_table.id = 7")
        assert "populate_existing" not in statement.get_execution_options()

    def test_by_id_locks_and_refreshes_on_request(self) -> None:
        statement = by_id(UserOrmModel, 3, *user_load_options(), for_update=True, refresh=True)

        sql = _sql(statement.limit(1))
        assert sql.endswith("WHERE user_table.id = 3 LIMIT 1 FOR NO KEY UPDATE")
        assert statement.get_execution_options()["populate_existing"] is True
        assert len(statement._with_options) == 1


class TestFetchPage:
    async def test_fetch_page_counts_then_reads_the_clamped_page(self) -> None:
        db = _RecordingSession(total=42, rows=["a", "b"])
        stmt = by_id(CustomerOrmModel, 1)

        total, rows = await fetch_page(
            db,  # type: ignore[arg-type]
            stmt,
            None,
            None,
            order_term(CustomerOrmModel.name, None, default="asc"),
            CustomerOrmModel.id.desc(),
        )

        assert (total, list(rows)) == (42, ["a", "b"])
        count_sql, page_sql = (_sql(s) for s in db.statements)
        assert count_sql.startswith("SELECT count(*) AS count_1 FROM (SELECT")
        assert "ORDER BY" not in count_sql
        assert page_sql.endswith(
            "ORDER BY customer_table.name ASC, customer_table.id DESC "
            f"LIMIT {DEFAULT_PAGE_SIZE} OFFSET 0"
        )

    async def test_fetch_page_keeps_existing_ordering_and_honours_min_limit(self) -> None:
        db = _RecordingSession(total=0, rows=[])
        stmt = by_id(CustomerOrmModel, 1).order_by(CustomerOrmModel.created)
        options = (selectinload(CustomerOrmModel.creator),)

        await fetch_page(
            db,  # type: ignore[arg-type]
            stmt,
            5,
            None,
            CustomerOrmModel.id,
            options=options,
            min_limit=DEFAULT_PAGE_SIZE + 10,
        )

        page = db.statements[1]
        assert _sql(page).endswith(
            "ORDER BY customer_table.created, customer_table.id "
            f"LIMIT {DEFAULT_PAGE_SIZE + 10} OFFSET 5"
        )
        assert page._with_options == options


class TestLoadByIds:
    async def test_load_by_ids_reads_the_id_list_into_a_list(self) -> None:
        db = _RecordingSession(total=0, rows=["m1", "m2"])

        rows = await load_by_ids(db, ProductionMachineOrmModel, [4, 2])  # type: ignore[arg-type]

        assert rows == ["m1", "m2"]
        assert isinstance(rows, list)
        assert _sql(db.statements[0]).endswith("WHERE production_machine_table.id IN (4, 2)")


class TestLoadUser:
    def test_load_user_appends_the_memberships_to_a_selectin_chain(self) -> None:
        built = load_user(MachinePoolOrmModel.machines, ProductionMachineOrmModel.creator)
        by_hand = (
            selectinload(MachinePoolOrmModel.machines)
            .selectinload(ProductionMachineOrmModel.creator)
            .selectinload(UserOrmModel.members)
        )

        assert [(e.path, e.strategy) for e in built.context] == [
            (e.path, e.strategy) for e in by_hand.context
        ]
