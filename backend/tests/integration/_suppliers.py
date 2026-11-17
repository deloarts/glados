"""
The supplier a test's orders and lines name by id. Creating an order line
checks that its supplier exists, so a test that names supplier #1 without
building one seeds it here. SQLite does not enforce foreign keys, so the
creator need not exist.
"""

from datetime import UTC
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)


async def seed_supplier(db: AsyncSession, supplier_id: int = 1) -> None:
    """Inserts supplier `supplier_id` unless it exists, and commits."""
    if await db.get(SupplierOrmModel, supplier_id) is not None:
        return
    now = datetime.now(UTC)
    db.add(
        SupplierOrmModel(
            id=supplier_id,
            created=now,
            changed=now,
            changes=[],
            archived=False,
            name=f"Supplier {supplier_id}",
            creator_id=1,
        )
    )
    await db.commit()
