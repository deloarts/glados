"""
Gives a lot seeded straight into the database the intents its stored status
stands for, and then lets the lifecycle reconciler store what its facts
derive for the lot and its positions, so the drift check after the test
agrees with the seed. A lot on hold gets its held_at, a canceled one its
canceled_at, a completed one its force-completion time, and a scrapped one a
quantity of zero, which rewrites the seeded quantity. Intents a seed set
already are kept. The positions' kinds, statuses and completed counts then
follow from the lines and production orders the seed gave them, and the
lot's status from its positions and intents. The derived lot status must be
the seeded one, so a seed cannot drift into another status unnoticed; a
caller that seeds a status its facts do not give on purpose passes
`exact=False`.
"""

from datetime import UTC
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface


class _Bus:
    async def publish(self, event: object) -> None:
        return None


_SEEDER = User(
    id=1,
    username="seed",
    full_name="Seed",
    email="seed@example.com",
    created=datetime(2026, 1, 1, tzinfo=UTC),
    hashed_password="x",
    is_active=True,
    is_systemuser=True,
    permissions=[],
    language=Language.enGB,
    date_format=DateFormat.ISO,
    start_page=StartPage.DASHBOARD,
    theme_preset=ThemePreset.Aura,
    theme_surface=ThemeSurface.glados,
    theme_primary=ThemePrimary.glados,
    theme_dark_mode=False,
    button_flat_style=False,
    table_gridlines=False,
    table_striped_rows=False,
)


async def give_lot_facts(db: AsyncSession, *lot_ids: int, exact: bool = True) -> None:
    """Records the intents of each lot's stored status and reconciles the
    lots, see the module docstring. Flushes, the caller commits."""
    now = datetime.now(UTC)
    seeded: dict[int, str] = {}
    for lot_id in lot_ids:
        lot = await db.get(ProductionLotOrmModel, lot_id, populate_existing=True)
        assert lot is not None, lot_id
        seeded[lot_id] = lot.status
        if lot.status == LotStatus.ON_HOLD.value and lot.held_at is None:
            lot.held_at = now
        elif lot.status == LotStatus.CANCELED.value and lot.canceled_at is None:
            lot.canceled_at = now
        elif lot.status == LotStatus.COMPLETED.value and lot.force_completed_at is None:
            lot.force_completed_at = lot.completed_at or now
        elif lot.status == LotStatus.SCRAPPED.value:
            lot.quantity = 0.0
    await db.flush()
    reconciler = LifecycleReconciler(sql_lifecycle_repositories(db), _Bus())
    reconciler.touch_lots(lot_ids)
    await reconciler.run(_SEEDER, now, reason="seeded")
    await db.flush()
    if exact:
        for lot_id, status in seeded.items():
            lot = await db.get(ProductionLotOrmModel, lot_id, populate_existing=True)
            assert lot is not None
            assert lot.status == status, (
                f"Lot #{lot_id} was seeded {status} but its facts derive {lot.status}."
            )


async def give_position_lot_facts(db: AsyncSession, *position_ids: int, exact: bool = True) -> None:
    """`give_lot_facts` for the lots of these positions."""
    lot_ids = await db.scalars(
        select(LotPositionOrmModel.lot_id).where(LotPositionOrmModel.id.in_(position_ids))
    )
    await give_lot_facts(db, *sorted(set(lot_ids)), exact=exact)
