"""
The race tests' own safety: a database that already holds tables is refused
before anything is created, and nothing in it is dropped. The session's
schema stands in for someone's data here, since the database holds it while
the tests run.
"""

import pytest
from sqlalchemy import Engine
from sqlalchemy import inspect

from tests.pg.conftest import DatabaseNotEmptyError
from tests.pg.conftest import throwaway_schema


def test_a_database_with_tables_is_refused_and_keeps_every_table(
    _postgres: str, schema_engine: Engine
) -> None:
    with schema_engine.connect() as connection:
        before = sorted(inspect(connection).get_table_names(schema="public"))
    assert before

    with pytest.raises(DatabaseNotEmptyError), throwaway_schema(_postgres):
        pytest.fail("A database with tables must be refused before it is used.")

    with schema_engine.connect() as connection:
        assert sorted(inspect(connection).get_table_names(schema="public")) == before
