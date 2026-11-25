"""
A lot step read from the production lot repository carries the wait of the
method that does it: its fabrication method's, or for an inspection step its
inspection method's. The schedule walk reads the wait from there.
"""

from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.inspection_method_repository import (
    SqlAlchemyInspectionMethodRepository,
)
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make


async def test_a_lot_step_carries_the_wait_of_its_method(db, create_user) -> None:
    owner = await create_user(username="owner", email="owner@example.com")
    graph = Graph(db, owner, owner)
    fabrication = await graph.fabrication_method()
    fabrication.wait_after_minutes = 90
    await SqlAlchemyFabricationMethodRepository(db).save(fabrication)
    inspection = await graph.inspection_method()
    inspection.wait_after_minutes = 240
    await SqlAlchemyInspectionMethodRepository(db).save(inspection)
    await db.commit()

    position = await graph.internal_position()
    lots = SqlAlchemyProductionLotRepository(db)
    await lots.save_step(
        make(
            LotStep,
            sequence=2,
            creator_id=owner.id,
            fabrication_method_id=None,
            lot_id=position.lot_id,
            position_id=position.id,
            source_process_id=None,
            role=StepRole.INSPECTION,
            inspection_method_id=inspection.id,
        )
    )
    await db.commit()

    lot = await lots.get_by_id(position.lot_id)
    assert lot is not None
    waits = {
        step.role: step.method_wait_after_minutes
        for lot_position in lot.positions
        for step in lot_position.steps
    }
    assert waits == {StepRole.FABRICATION: 90, StepRole.INSPECTION: 240}
