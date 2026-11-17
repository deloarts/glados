"""
Concrete SQLAlchemy implementation of IReportJournalRepository. Append
only, except for blanking the addresses of an anonymised person: save()
only flushes; the caller's unit of work commits the row.
"""

from functools import lru_cache
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.quality.adapters.outbound.persistence.models.report_journal_model import (
    ReportJournalOrmModel,
)
from src.modules.quality.domain.entities.report_journal_entry import ReportJournalEntry
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.domain.value_objects.report_journal import ReportJournalAction


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    return (load_user(ReportJournalOrmModel.actor),)


def _orm_to_entity(orm: ReportJournalOrmModel) -> ReportJournalEntry:
    created = utc_aware(orm.created)
    assert created is not None  # non-null column
    return ReportJournalEntry(
        id=orm.id,
        public_id=orm.public_id,
        created=created,
        actor_id=orm.actor_id,
        action=ReportJournalAction(orm.action),
        document=UploadedPrintDocument(orm.document),
        root_type=PrintRootType(orm.root_type),
        root_id=orm.root_id,
        lineage=orm.lineage,
        revision=orm.revision,
        language=orm.language,
        options={str(k): bool(v) for k, v in (orm.options or {}).items()},
        report_version=orm.report_version,
        engine_version=orm.engine_version,
        byte_size=orm.byte_size,
        sha256=orm.sha256,
        print_job_id=orm.print_job_id,
        copies=orm.copies,
        recipients=list(orm.recipients) if orm.recipients is not None else None,
        actor_full_name=orm.actor.full_name if orm.actor else "",
    )


class SqlAlchemyReportJournalRepository:
    """Implements IReportJournalRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, item: ReportJournalEntry) -> ReportJournalEntry:
        orm = ReportJournalOrmModel(
            created=item.created,
            actor_id=item.actor_id,
            action=item.action.value,
            document=item.document.value,
            root_type=item.root_type.value,
            root_id=item.root_id,
            lineage=item.lineage,
            revision=item.revision,
            language=item.language,
            options=item.options,
            report_version=item.report_version,
            engine_version=item.engine_version,
            byte_size=item.byte_size,
            sha256=item.sha256,
            print_job_id=item.print_job_id,
            copies=item.copies,
            recipients=list(item.recipients) if item.recipients is not None else None,
        )
        self._db.add(orm)
        await self._db.flush()
        loaded = (
            await self._db.scalars(
                select(ReportJournalOrmModel)
                .where(ReportJournalOrmModel.id == orm.id)
                .options(*_load_options())
            )
        ).one()
        return _orm_to_entity(loaded)

    async def count_for_lineages(self, root_type: str, lineages: list[UUID]) -> int:
        if not lineages:
            return 0
        count = await self._db.scalar(
            select(func.count(ReportJournalOrmModel.id)).where(
                ReportJournalOrmModel.root_type == root_type,
                ReportJournalOrmModel.lineage.in_(lineages),
            )
        )
        return count or 0

    async def list_for_lineage(self, root_type: str, lineage: UUID) -> list[ReportJournalEntry]:
        rows = (
            await self._db.scalars(
                select(ReportJournalOrmModel)
                .where(
                    ReportJournalOrmModel.root_type == root_type,
                    ReportJournalOrmModel.lineage == lineage,
                )
                .options(*_load_options())
                .order_by(desc(ReportJournalOrmModel.created), desc(ReportJournalOrmModel.id))
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def set_recipients_blank(self, entry_ids: list[int], addresses: set[str]) -> None:
        if not entry_ids or not addresses:
            return
        rows = await self._db.scalars(
            select(ReportJournalOrmModel).where(ReportJournalOrmModel.id.in_(entry_ids))
        )
        for row in rows:
            if not row.recipients:
                continue
            row.recipients = [
                "" if address.casefold() in addresses else address for address in row.recipients
            ]
        await self._db.flush()
