"""
Alembic autogenerate callbacks and the hand-maintained-object exclusion
list, shared between alembic/env.py (which wires them into every real
migration run) and tests/integration/test_migrations_postgres.py (which
runs the same drift check standalone against a Postgres connection).
Kept here, outside alembic/env.py, so the test can import `include_object`
and `compare_server_default` without importing Alembic's env module, which
has import-time side effects, overriding `sqlalchemy.url` from Settings and
configuring logging, that a test process should not trigger as a side
effect of a plain import.

`TRGM_INDEX_COLUMNS` and `LOG_TRGM_INDEX_COLUMNS` mirror the trigram
column list of the initial migration. Those single-column GIN trigram
indexes, like the `ix_bought_item_trgm_search` expression index beside them,
are created via raw `op.execute()`, not declared on any ORM model, so they
must all be excluded from autogenerate comparison, or
`alembic revision --autogenerate` proposes dropping every one of them.
Declaring any of these as a normal SQLAlchemy Index instead risks a
byte-for-byte mismatch against Postgres's own normalised rendering of the
expression, which would make `alembic check` flag a spurious add+remove
pair forever instead of converging.
"""

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy import FetchedValue

# (table, column) pairs backing the 31 single-column GIN trigram indexes
# created by the initial migration: the tier-A + tier-B columns of every
# resource the search endpoint covers, plus the document number search.
TRGM_INDEX_COLUMNS: tuple[tuple[str, str], ...] = (
    ("product_table", "product_number"),
    ("product_table", "description"),
    ("project_table", "project_number"),
    ("project_table", "description"),
    ("bought_item_table", "article_name"),
    ("bought_item_table", "order_code_1"),
    ("bought_item_table", "order_code_2"),
    ("bought_item_table", "part_number"),
    ("bought_item_table", "gtin"),
    ("bought_item_table", "ean"),
    ("bought_item_table", "note"),
    ("made_item_table", "article_name"),
    ("made_item_table", "part_number"),
    ("made_item_table", "material"),
    ("made_item_table", "note"),
    ("source_item_table", "material"),
    ("source_item_table", "order_code_1"),
    ("source_item_table", "order_code_2"),
    ("source_item_table", "dimension"),
    ("source_item_table", "note"),
    ("order_table", "order_number"),
    ("order_table", "note"),
    ("order_table", "storage_place"),
    ("production_lot_table", "lot_number"),
    ("production_lot_table", "note"),
    ("production_order_table", "production_order_number"),
    ("production_order_table", "note"),
    ("calculation_table", "document_number"),
    ("calculation_table", "title"),
    ("checklist_table", "document_number"),
    ("checklist_table", "title"),
)

# (table, column) pairs of the trigram indexes behind the log view's
# substring filters, created by the initial migration the same way.
LOG_TRGM_INDEX_COLUMNS: tuple[tuple[str, str], ...] = (
    ("log_table", "message"),
    ("log_table", "path"),
)

# Objects the initial migration creates with hand-written `op.execute()` DDL
# that are deliberately not declared on any ORM model. Named
# explicitly, not a blanket ignore, so a real new drift on the same table
# still surfaces.
HAND_MAINTAINED_OBJECTS: frozenset[tuple[str, str]] = frozenset(
    {("index", "ix_bought_item_trgm_search")}
    | {
        ("index", f"ix_{table}_{column}_trgm")
        for table, column in TRGM_INDEX_COLUMNS + LOG_TRGM_INDEX_COLUMNS
    }
)


def include_object(
    obj: "sa.schema.SchemaItem", name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    return (type_, name) not in HAND_MAINTAINED_OBJECTS


def compare_server_default(
    ctx: object,
    insp_col: "Column[object]",
    meta_col: "Column[object]",
    insp_default: str | None,
    meta_default: FetchedValue | None,
    rendered: str | None,
) -> bool | None:
    """
    Postgres defines no `=` for plain json; the generic probe issues
    SELECT '<default>'::json = '<default>' and raises UndefinedFunction.
    Skip those columns rather than disabling the comparison globally.
    """
    if isinstance(insp_col.type, sa.JSON) or isinstance(meta_col.type, sa.JSON):
        return False  # False == "no difference"
    return None  # None == "fall through to the default comparison"
