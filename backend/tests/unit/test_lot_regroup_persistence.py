"""
Regroup/step-delete tests against a REAL SQLAlchemy session on a
throwaway in-memory SQLite engine, rather than the fake repository the
rest of the production-lot unit tests use.

Why this file exists: LotPositionOrmModel.steps cascades
"all, delete-orphan", and RegroupLotPositions repoints a step by writing
its position_id column, which never updates an already-loaded `steps`
collection on the step's OLD position. Deleting that old position could
then cascade-delete steps that have just been moved to a different
position, silent data loss on a live regroup. The fake repository models
no ORM cascade at all, so only a real session can catch this class of bug.
"""

import importlib
from collections.abc import AsyncIterator
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import selectinload

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.application.dto.production_lot_dto import RegroupLotPositionsCommand
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import (
    RegroupLotPositions,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface

# Import every model module directly so Base.metadata is complete for
# create_all() to resolve every FK (same reason as test_change_tracking.py).
for _module_name in model_module_names():
    importlib.import_module(_module_name)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


class _Bus:
    async def publish(self, event: object) -> None:
        return None


def _reconciler(session: AsyncSession) -> LifecycleReconciler:
    """The lifecycle reconciler on the test's session, as a request has it."""
    return LifecycleReconciler(sql_lifecycle_repositories(session), _Bus())


class FakeUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


def make_actor() -> User:
    return User(
        id=1,
        username="tester",
        full_name="Tester",
        email="tester@example.com",
        created=NOW,
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=["write:lots", "manage:lots"],
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


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db
    await engine.dispose()


@pytest.fixture
async def lot_with_qa_position(session: AsyncSession) -> dict[str, list[int]]:
    """The exact shape a require_qa lot is born with: two fabrication
    positions (the second holding two grouped steps) plus the auto-QA
    singleton, which is born INTERNAL with a queued order."""
    session.add(
        UserOrmModel(
            id=1,
            created=NOW,
            username="tester",
            full_name="Tester",
            email="tester@example.com",
            hashed_password="x",
        )
    )
    session.add(
        ProductionLotOrmModel(
            id=1,
            created=date(2026, 8, 17),
            changed=None,
            changes=[],
            lot_number="LOT-REGROUP",
            quantity=1.0,
            status="draft",
            priority="normal",
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
    )

    def position(id: int, sequence: int, kind: str) -> LotPositionOrmModel:
        return LotPositionOrmModel(
            id=id,
            created=date(2026, 8, 17),
            changed=None,
            changes=[],
            sequence=sequence,
            kind=kind,
            status="pending" if kind == LotPositionKind.UNASSIGNED.value else "ordered_or_queued",
            quantity=1.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=1,
        )

    def step(id: int, sequence: int, position_id: int, role: str) -> LotStepOrmModel:
        is_fabrication = role == StepRole.FABRICATION.value
        return LotStepOrmModel(
            id=id,
            created=NOW,
            note=None,
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            sequence=sequence,
            creator_id=1,
            fabrication_method_id=1 if is_fabrication else None,
            lot_id=1,
            position_id=position_id,
            source_process_id=None,
            role=role,
            inspection_method_id=None if is_fabrication else 1,
        )

    session.add_all(
        [
            position(10, 1, LotPositionKind.UNASSIGNED.value),
            position(11, 2, LotPositionKind.UNASSIGNED.value),
            position(12, 3, LotPositionKind.INTERNAL.value),
        ]
    )
    session.add_all(
        [
            step(101, 1, 10, StepRole.FABRICATION.value),
            step(102, 2, 11, StepRole.FABRICATION.value),
            step(103, 3, 11, StepRole.FABRICATION.value),
            step(104, 4, 12, StepRole.INSPECTION.value),
        ]
    )
    await session.commit()
    return {"steps": [101, 102, 103, 104], "positions": [10, 11, 12]}


async def regroup(session: AsyncSession, groups: list[list[int]]) -> None:
    repo = SqlAlchemyProductionLotRepository(session)
    await RegroupLotPositions(
        repo, uow=FakeUnitOfWork(session), reconciler=_reconciler(session)
    ).execute(make_actor(), 1, RegroupLotPositionsCommand(groups=groups))
    session.expire_all()


async def surviving_steps(session: AsyncSession) -> dict[int, int]:
    """step id -> position id, for every step still in the database."""
    return {
        s.id: s.position_id
        for s in (
            await session.scalars(select(LotStepOrmModel).order_by(LotStepOrmModel.sequence))
        ).all()
    }


async def test_deleting_a_position_never_takes_repointed_steps_with_it(
    session: AsyncSession, lot_with_qa_position
):
    """The cascade guarantee itself, at the repository level.

    This is the exact sequence a regroup performs, with the one condition
    that makes it destructive spelled out rather than left to whichever
    internal read happens to produce it: position #11's `steps`
    collection is LOADED before its steps are moved away. Writing
    position_id does not update that loaded collection, so without
    _refresh_steps_before_delete the delete-orphan cascade deletes steps
    102 and 103, which is precisely how LN-26-00029 and LN-26-00023 lost
    their steps 2 and 3.
    """
    repo = SqlAlchemyProductionLotRepository(session)
    old_position = await session.get(
        LotPositionOrmModel, 11, options=[selectinload(LotPositionOrmModel.steps)]
    )
    assert old_position is not None

    # Any read of the lot does this; making it explicit keeps the test
    # honest about what it is reproducing.
    assert [s.id for s in old_position.steps] == [102, 103]
    assert "steps" not in inspect(old_position).unloaded

    # Move both steps onto a different position, exactly as a regroup does.
    target = await repo.get_position_by_id(10)
    assert target is not None
    for step in await repo.get_steps(1):
        if step.position_id == 11:
            step.position_id = target.id
            await repo.save_step(step)

    await repo.delete_position(await repo.get_position_by_id(11))
    await session.commit()
    session.expire_all()

    assert await surviving_steps(session) == {101: 10, 102: 10, 103: 10, 104: 12}


async def test_ungrouping_keeps_every_step(session: AsyncSession, lot_with_qa_position):
    # "Remove the grouping": split the paired steps into their own
    # positions. Steps 102/103 move off position 11, which is then
    # deleted, and the cascade must not take them with it.
    await regroup(session, [[101], [102], [103], [104]])

    steps = await surviving_steps(session)
    assert sorted(steps) == [101, 102, 103, 104]
    # Each step now sits alone in its own position.
    assert len(set(steps.values())) == 4
    assert steps[101] == 10, "an unchanged group keeps its original position row"
    assert steps[104] == 12, "the born-INTERNAL QA position is preserved, not recreated"

    positions = (
        await session.scalars(select(LotPositionOrmModel).order_by(LotPositionOrmModel.sequence))
    ).all()
    assert [p.sequence for p in positions] == [1, 2, 3, 4]
    assert await session.get(LotPositionOrmModel, 11) is None, "the emptied old position is gone"


async def test_regrouping_into_one_position_keeps_every_step(
    session: AsyncSession, lot_with_qa_position
):
    # The reverse direction: both fabrication positions merge into one.
    # Every old fabrication position is deleted here, so a stale-cascade
    # bug would wipe all three of their steps at once.
    await regroup(session, [[101, 102, 103], [104]])

    steps = await surviving_steps(session)
    assert sorted(steps) == [101, 102, 103, 104]
    assert steps[101] == steps[102] == steps[103], "the three steps share one new position"
    assert steps[104] == 12


async def test_reordering_positions_renumbers_them_without_unique_collisions(
    session: AsyncSession, lot_with_qa_position
):
    """The whole point of dragging a position: LotPosition.sequence has to
    follow. Both renumbering passes run against a live
    UNIQUE(lot_id, sequence), which a naive one-pass update would trip."""
    from src.modules.fulfillment.application.dto.production_lot_dto import ReorderLotStepsCommand
    from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import (
        ReorderLotSteps,
    )

    repo = SqlAlchemyProductionLotRepository(session)
    # Drag the second fabrication position (steps 102 and 103) to the front
    # of the lot; the QA position, which is assigned, keeps its place.
    await ReorderLotSteps(
        repo, uow=FakeUnitOfWork(session), reconciler=_reconciler(session)
    ).execute(make_actor(), 1, ReorderLotStepsCommand(ordered_step_ids=[102, 103, 101, 104]))
    session.expire_all()

    positions = (
        await session.scalars(select(LotPositionOrmModel).order_by(LotPositionOrmModel.sequence))
    ).all()
    assert [(p.id, p.sequence) for p in positions] == [(11, 1), (10, 2), (12, 3)]
    assert await surviving_steps(session) == {104: 12, 101: 10, 102: 11, 103: 11}


async def test_regroup_leaves_the_qa_production_order_intact(
    session: AsyncSession, lot_with_qa_position
):
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
        ProductionOrderOrmModel,
    )

    session.add(
        ProductionOrderOrmModel(
            id=1,
            created=NOW,
            changes=[],
            production_order_number="PO-1",
            status="queued",
            priority="normal",
            quantity=1.0,
            quantity_completed=0.0,
            lot_position_id=12,
            creator_id=1,
        )
    )
    await session.commit()

    await regroup(session, [[101], [102], [103], [104]])

    order = await session.get(ProductionOrderOrmModel, 1)
    assert order is not None, "the QA order's position survives, so its order must too"
    assert order.lot_position_id == 12
