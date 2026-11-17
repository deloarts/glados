"""
Part numbers and the numbers of calculations, checklists and sequences come
from their families' counters: two draws never return the same number, even
before either is claimed or saved, and the families count separately.
"""

import pytest

from src.modules.catalogue.adapters.outbound.persistence.repositories.part_number_registry_repository import (
    SqlAlchemyPartNumberRegistryRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.calculation_repository import (
    SqlAlchemyCalculationRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.checklist_repository import (
    SqlAlchemyChecklistRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.sequence_repository import (
    SqlAlchemySequenceRepository,
)


async def test_two_part_number_draws_before_a_claim_differ(db) -> None:
    registry = SqlAlchemyPartNumberRegistryRepository(db)

    drawn = [await registry.next_part_number("PN-{seq:04d}") for _ in range(2)]

    assert drawn == ["PN-0001", "PN-0002"]


@pytest.mark.parametrize(
    "repository",
    [SqlAlchemyCalculationRepository, SqlAlchemyChecklistRepository, SqlAlchemySequenceRepository],
)
async def test_two_document_number_draws_before_a_save_differ(db, repository) -> None:
    documents = repository(db)

    drawn = [await documents.next_document_number("DOC-{seq:03d}") for _ in range(2)]

    assert drawn == ["DOC-001", "DOC-002"]


async def test_document_families_count_the_same_prefix_separately(db) -> None:
    calculation = await SqlAlchemyCalculationRepository(db).next_document_number("D-{seq}")
    checklist = await SqlAlchemyChecklistRepository(db).next_document_number("D-{seq}")

    assert (calculation, checklist) == ("D-1", "D-1")
