"""
SQLAlchemy implementation of IProductVariantRepository. Writes only flush;
the caller's unit of work commits them. Archived rows are written before
renamed live ones, so a name moving from one variant to another never
meets itself in the live-name index.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.workspace.adapters.outbound.persistence.models.product_variant_model import (
    ProductVariantOrmModel,
)
from src.modules.workspace.domain.entities.product_variant import ProductVariant
from src.modules.workspace.ports.outbound.repositories.product_variant_repository import (
    IProductVariantRepository,
)


def _to_entity(orm: ProductVariantOrmModel) -> ProductVariant:
    return ProductVariant(
        id=orm.id,
        public_id=orm.public_id,
        product_id=orm.product_id,
        name=orm.name,
        sort_order=orm.sort_order,
        archived=orm.archived,
    )


class SqlAlchemyProductVariantRepository(IProductVariantRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_product(self, product_id: int, include_archived: bool) -> list[ProductVariant]:
        m = ProductVariantOrmModel
        q = select(m).where(m.product_id == product_id)
        if not include_archived:
            q = q.where(m.archived.is_(False))
        rows = await self._db.scalars(q.order_by(m.archived, m.sort_order, m.id))
        return [_to_entity(r) for r in rows]

    async def save_all(
        self, product_id: int, variants: list[ProductVariant]
    ) -> list[ProductVariant]:
        m = ProductVariantOrmModel
        stored = {
            row.id: row
            for row in await self._db.scalars(select(m).where(m.product_id == product_id))
        }
        for variant in variants:
            if variant.id and variant.id not in stored:
                raise ValueError(f"Variant id={variant.id} is not one of product {product_id}.")
        # First archive what goes and park the kept names, so a name that
        # moves from one variant to another never meets itself in the
        # live-name index; then write the final names and the new rows.
        for variant in variants:
            if variant.id:
                row = stored[variant.id]
                row.archived = variant.archived
                if not variant.archived:
                    row.name = f"\x00{variant.id}"
        await self._db.flush()
        for variant in variants:
            if variant.id == 0:
                self._db.add(
                    m(
                        product_id=product_id,
                        name=variant.name,
                        sort_order=variant.sort_order,
                        archived=False,
                    )
                )
            elif not variant.archived:
                stored[variant.id].name = variant.name
                stored[variant.id].sort_order = variant.sort_order
        await self._db.flush()
        return await self.get_by_product(product_id, include_archived=True)
