"""
Removal of quote request lines and demand shares when what they name goes
away. The foreign keys cascade on Postgres; the test database runs without
foreign key enforcement, so the rows are removed here explicitly, and the
order lines and offer extra costs that named a removed line keep standing
without it.
"""

from sqlalchemy import ColumnElement
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteExtraCostOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineDemandOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)


async def delete_quote_request_lines(db: AsyncSession, where: ColumnElement[bool]) -> None:
    """Deletes the quote request lines `where` selects with their offers and
    demand shares; an offer extra cost, an order line or a replaced line
    that named one of them keeps standing without the link."""
    ids = list((await db.scalars(select(QuoteRequestLineOrmModel.id).where(where))).all())
    if not ids:
        return
    await db.execute(delete(QuoteOrmModel).where(QuoteOrmModel.line_id.in_(ids)))
    await db.execute(
        update(QuoteExtraCostOrmModel)
        .where(QuoteExtraCostOrmModel.line_id.in_(ids))
        .values(line_id=None)
    )
    await db.execute(
        update(QuoteRequestLineOrmModel)
        .where(QuoteRequestLineOrmModel.substituted_by_line_id.in_(ids))
        .values(substituted_by_line_id=None)
        .execution_options(synchronize_session=False)
    )
    await db.execute(
        update(OrderItemOrmModel)
        .where(OrderItemOrmModel.quote_request_line_id.in_(ids))
        .values(quote_request_line_id=None)
        .execution_options(synchronize_session=False)
    )
    await db.execute(
        delete(QuoteRequestLineDemandOrmModel).where(
            QuoteRequestLineDemandOrmModel.line_id.in_(ids)
        )
    )
    await db.execute(
        delete(QuoteRequestLineOrmModel)
        .where(QuoteRequestLineOrmModel.id.in_(ids))
        .execution_options(synchronize_session="fetch")
    )


async def delete_demand_shares(db: AsyncSession, where: ColumnElement[bool]) -> None:
    """Deletes the demand shares `where` selects, those of a demand that is
    deleted; the line stays on its request."""
    await db.execute(
        delete(QuoteRequestLineDemandOrmModel)
        .where(where)
        .execution_options(synchronize_session="fetch")
    )
