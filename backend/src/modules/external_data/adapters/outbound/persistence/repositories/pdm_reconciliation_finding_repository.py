"""
Concrete implementation of IPdmReconciliationFindingRepository using
SQLAlchemy.
"""

from typing import Any

from sqlalchemy import asc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.external_data.adapters.outbound.persistence.models.pdm_reconciliation_finding_model import (
    PdmReconciliationFindingOrmModel,
)
from src.modules.external_data.domain.entities.pdm_reconciliation_finding import (
    PdmReconciliationFinding,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_severity import (
    PdmReconciliationSeverity,
)
from src.modules.external_data.ports.outbound.repositories.pdm_reconciliation_finding_repository import (
    PdmReconciliationFindingFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page


def _orm_to_entity(orm: PdmReconciliationFindingOrmModel) -> PdmReconciliationFinding:
    return PdmReconciliationFinding(
        id=orm.id,
        public_id=orm.public_id,
        run_id=orm.run_id,
        category=PdmReconciliationCategory(orm.category),
        severity=PdmReconciliationSeverity(orm.severity),
        kind=orm.kind,
        item_id=orm.item_id,
        file_id=orm.file_id,
        part_number=orm.part_number,
        revision=orm.revision,
        message=orm.message,
        count=orm.count,
        created_at=utc_aware(orm.created_at),
    )


def _entity_to_dict(finding: PdmReconciliationFinding) -> dict[str, Any]:
    return {
        "run_id": finding.run_id,
        "category": finding.category.value,
        "severity": finding.severity.value,
        "kind": finding.kind,
        "item_id": finding.item_id,
        "file_id": finding.file_id,
        "part_number": finding.part_number,
        "revision": finding.revision,
        "message": finding.message,
        "count": finding.count,
        "created_at": finding.created_at,
    }


class SqlAlchemyPdmReconciliationFindingRepository:
    """Implements IPdmReconciliationFindingRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add_many(self, findings: list[PdmReconciliationFinding]) -> None:
        for finding in findings:
            self._db.add(PdmReconciliationFindingOrmModel(**_entity_to_dict(finding)))
        await self._db.flush()

    async def get_multi(
        self, run_id: int, filters: PdmReconciliationFindingFilterDto
    ) -> tuple[int, list[PdmReconciliationFinding]]:
        q = select(PdmReconciliationFindingOrmModel).where(
            PdmReconciliationFindingOrmModel.run_id == run_id
        )
        if filters.category:
            q = q.where(PdmReconciliationFindingOrmModel.category == filters.category)
        if filters.kind:
            q = q.where(PdmReconciliationFindingOrmModel.kind == filters.kind)
        if filters.search:
            term = filters.search
            q = q.where(
                or_(
                    contains_ci(PdmReconciliationFindingOrmModel.part_number, term),
                    contains_ci(PdmReconciliationFindingOrmModel.message, term),
                )
            )
        if filters.part_number:
            q = q.where(
                contains_ci(PdmReconciliationFindingOrmModel.part_number, filters.part_number)
            )
        if filters.message:
            q = q.where(contains_ci(PdmReconciliationFindingOrmModel.message, filters.message))

        total, rows = await fetch_page(
            self._db, q, filters.skip, filters.limit, asc(PdmReconciliationFindingOrmModel.id)
        )
        return total, [_orm_to_entity(r) for r in rows]

    async def counts_for_run(self, run_id: int) -> dict[str, int]:
        rows = (
            await self._db.execute(
                select(
                    PdmReconciliationFindingOrmModel.category,
                    func.sum(PdmReconciliationFindingOrmModel.count).label("total"),
                )
                .where(PdmReconciliationFindingOrmModel.run_id == run_id)
                .group_by(PdmReconciliationFindingOrmModel.category)
            )
        ).all()
        return {row.category: int(row.total) for row in rows}
