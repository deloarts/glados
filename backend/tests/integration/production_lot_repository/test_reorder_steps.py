"""
reorder_steps against lot_step_table's UNIQUE(lot_id, sequence), which is
not deferrable. Writing the final sequences straight onto the ORM rows
would make SQLAlchemy emit one UPDATE per row, so the first row to move
would land on a sequence another row still holds and the commit would fail
with an IntegrityError that no exception handler maps, a 500 rather than a
clean rejection. Only a real database can show this, since the unit tests
substitute an in-memory fake repository with no constraints (see
tests/unit/production_lot/).
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project


async def _make_lot_with_steps(db, creator_id: int, step_count: int) -> tuple[int, list[int]]:
    """Builds a lot carrying `step_count` steps at sequences 1..N, all in a
    single unassigned position. Returns (lot_id, step_ids in sequence)."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0, created=datetime.now(UTC), creator_id=creator_id, project_number="P-REORDER-1"
        )
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name="Reorder target",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    method = await SqlAlchemyFabricationMethodRepository(db).save(
        FabricationMethod(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "Turning"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )

    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number="LN-REORDER-1",
            quantity=10.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.UNASSIGNED,
            status=LotPositionStatus.PENDING,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )

    step_ids: list[int] = []
    for sequence in range(1, step_count + 1):
        step = await lot_repo.save_step(
            LotStep(
                id=0,
                created=datetime.now(UTC),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=sequence,
                creator_id=creator_id,
                fabrication_method_id=method.id,
                lot_id=lot.id,
                position_id=position.id,
                source_process_id=None,
            )
        )
        step_ids.append(step.id)
    return lot.id, step_ids


class TestReorderSteps:
    async def test_swapping_two_steps_does_not_violate_the_sequence_constraint(
        self, db, create_user
    ):
        """Both target sequences are already occupied, so a naive
        one-UPDATE-per-row rewrite would collide."""
        user = await create_user()
        lot_id, [first, second] = await _make_lot_with_steps(db, user.id, 2)

        repo = SqlAlchemyProductionLotRepository(db)
        reordered = await repo.reorder_steps(lot_id, [second, first])

        assert [s.id for s in reordered] == [second, first]
        assert [s.sequence for s in reordered] == [1, 2]

    async def test_full_reversal_renumbers_every_step(self, db, create_user):
        user = await create_user()
        lot_id, step_ids = await _make_lot_with_steps(db, user.id, 4)

        repo = SqlAlchemyProductionLotRepository(db)
        reordered = await repo.reorder_steps(lot_id, list(reversed(step_ids)))

        assert [s.id for s in reordered] == list(reversed(step_ids))
        assert [s.sequence for s in reordered] == [1, 2, 3, 4]

    async def test_leaves_no_temporary_negative_sequences_behind(self, db, create_user):
        """reorder_steps parks rows at negative sequences mid-flight; none may
        survive the commit, or the next reorder would read them back."""
        user = await create_user()
        lot_id, step_ids = await _make_lot_with_steps(db, user.id, 3)

        repo = SqlAlchemyProductionLotRepository(db)
        await repo.reorder_steps(lot_id, [step_ids[2], step_ids[0], step_ids[1]])
        # A second reorder only works if the first one settled cleanly.
        reordered = await repo.reorder_steps(lot_id, step_ids)

        assert [s.sequence for s in reordered] == [1, 2, 3]
        assert all(s.sequence > 0 for s in reordered)
        assert [s.id for s in reordered] == step_ids
