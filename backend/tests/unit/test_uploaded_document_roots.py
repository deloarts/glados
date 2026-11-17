"""
Each kind of uploaded document resolves to its own record and only for an
actor who may see that record; a hidden record answers like a missing one.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4

import pytest

from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoots
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.errors import CalculationNotFoundError
from src.modules.quality.domain.errors import ChecklistNotFoundError
from src.modules.quality.domain.value_objects.checklist_answer import ChecklistVerdict
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from tests.factories import make_user


def make_checklist(creator_id: int = 1, project_id: int | None = 5) -> Checklist:
    return Checklist(
        id=31,
        public_id=uuid4(),
        created=datetime.now(UTC),
        changed=None,
        changes=[],
        type="hydraulics",
        title="Press 12",
        header={},
        answers={},
        remarks={},
        definition_version=1,
        item_count=10,
        answered_count=0,
        finding_count=0,
        verdict=ChecklistVerdict.OPEN,
        project_id=project_id,
        product_id=None,
        lineage=uuid4(),
        revision="A",
        revision_reason=None,
        is_latest=True,
        superseded_at=None,
        creator_id=creator_id,
        released_at=None,
        released_by_id=None,
    )


def make_calculation() -> Calculation:
    return Calculation(
        id=42,
        public_id=uuid4(),
        created=datetime.now(UTC),
        changed=None,
        changes=[],
        tool="drive_sizing",
        title="Lift axis",
        note=None,
        inputs={},
        results={},
        input_version=1,
        engine_version=1,
        project_id=None,
        product_id=7,
        creator_id=1,
        released_at=None,
        released_by_id=None,
    )


class FakeRepository:
    def __init__(self, records: list) -> None:
        self._by_public_id = {record.public_id: record for record in records}

    async def get_by_public_id(self, public_id: UUID):
        return self._by_public_id.get(public_id)


def roots(
    calculations: list | None = None, checklists: list | None = None
) -> UploadedDocumentRoots:
    return UploadedDocumentRoots(
        FakeRepository(calculations or []),  # type: ignore[arg-type]
        FakeRepository(checklists or []),  # type: ignore[arg-type]
    )


async def test_uploaded_document_roots_resolve_a_calculation() -> None:
    calculation = make_calculation()

    resolved = await roots(calculations=[calculation]).resolve(
        make_user(), UploadedPrintDocument.CALCULATION_REPORT, calculation.public_id
    )

    assert resolved == (PrintRootType.CALCULATION, 42)


async def test_uploaded_document_roots_resolve_a_checklist() -> None:
    checklist = make_checklist()

    resolved = await roots(checklists=[checklist]).resolve(
        make_user(), UploadedPrintDocument.CHECKLIST_REPORT, checklist.public_id
    )

    assert resolved == (PrintRootType.CHECKLIST, 31)


async def test_uploaded_document_roots_hide_another_users_personal_checklist() -> None:
    checklist = make_checklist(creator_id=99, project_id=None)

    with pytest.raises(ChecklistNotFoundError):
        await roots(checklists=[checklist]).resolve(
            make_user(), UploadedPrintDocument.CHECKLIST_REPORT, checklist.public_id
        )


async def test_uploaded_document_roots_do_not_mix_up_kinds() -> None:
    checklist = make_checklist()

    with pytest.raises(CalculationNotFoundError):
        await roots(checklists=[checklist]).resolve(
            make_user(), UploadedPrintDocument.CALCULATION_REPORT, checklist.public_id
        )


async def test_uploaded_document_roots_describe_a_lot_as_its_own_lineage() -> None:
    lot = SimpleNamespace(id=187, public_id=uuid4())
    resolver = UploadedDocumentRoots(
        FakeRepository([]),  # type: ignore[arg-type]
        FakeRepository([]),  # type: ignore[arg-type]
        FakeRepository([lot]),  # type: ignore[arg-type]
    )

    root = await resolver.describe(
        make_user(), UploadedPrintDocument.INSPECTION_REPORT, lot.public_id
    )

    assert (root.root_type, root.root_id, root.lineage, root.revision) == (
        PrintRootType.PRODUCTION_LOT,
        187,
        lot.public_id,
        "",
    )
    with pytest.raises(LotNotFoundError):
        await resolver.describe(make_user(), UploadedPrintDocument.INSPECTION_REPORT, uuid4())
