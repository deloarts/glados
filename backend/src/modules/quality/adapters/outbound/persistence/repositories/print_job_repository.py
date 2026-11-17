"""
Concrete implementation of IPrintJobRepository using SQLAlchemy + Postgres.
Rows are history; the only update and delete are the auto-print claim's
finish and release. Every method only flushes; the caller's unit of work
commits.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import delete
from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.quality.adapters.outbound.persistence.models.print_job_model import (
    PrintJobOrmModel,
)
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.ports.outbound.repositories.print_job_repository import PrintJobFilterDto


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences. Built on first call rather
    than at import, because constructing a loader option configures the mapper
    registry before every model module is registered."""
    return (load_user(PrintJobOrmModel.actor),)


def _orm_to_entity(orm: PrintJobOrmModel) -> PrintJob:
    return PrintJob(
        id=orm.id,
        public_id=orm.public_id,
        created=orm.created,
        template_id=orm.template_id,
        printer_id=orm.printer_id,
        classifier=_job_classifier(orm.classifier),
        root_type=PrintRootType(orm.root_type),
        root_id=orm.root_id,
        copies=orm.copies,
        status=PrintJobStatus(orm.status),
        error_message=orm.error_message,
        rendered_zpl=orm.rendered_zpl,
        document_bytes=orm.document_bytes,
        trigger=PrintJobTrigger(orm.trigger),
        source_event_id=orm.source_event_id,
        actor_id=orm.actor_id,
        actor_full_name=user_orm_to_entity(orm.actor).full_name if orm.actor else "",
    )


def _entity_to_dict(item: PrintJob) -> dict[str, Any]:
    return {
        "created": item.created,
        "template_id": item.template_id,
        "printer_id": item.printer_id,
        "classifier": item.classifier.value,
        "root_type": item.root_type.value,
        "root_id": item.root_id,
        "copies": item.copies,
        "status": item.status.value,
        "error_message": item.error_message,
        "rendered_zpl": item.rendered_zpl,
        "document_bytes": item.document_bytes,
        "trigger": item.trigger.value,
        "source_event_id": item.source_event_id,
        "actor_id": item.actor_id,
    }


class SqlAlchemyPrintJobRepository:
    """Implements IPrintJobRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, item: PrintJob) -> PrintJob:
        orm = PrintJobOrmModel(**_entity_to_dict(item))
        self._db.add(orm)
        await self._db.flush()
        return await self._reload(orm.id)

    async def get_multi(self, filters: PrintJobFilterDto) -> tuple[int, list[PrintJob]]:
        q = select(PrintJobOrmModel)

        if filters.classifier:
            q = q.where(PrintJobOrmModel.classifier == filters.classifier)
        if filters.root_type:
            q = q.where(PrintJobOrmModel.root_type == filters.root_type)
        if filters.root_id:
            q = q.where(PrintJobOrmModel.root_id == filters.root_id)
        if filters.printer_id:
            q = q.where(PrintJobOrmModel.printer_id == filters.printer_id)
        if filters.status:
            q = q.where(PrintJobOrmModel.status == filters.status)

        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            desc(PrintJobOrmModel.created),
            options=_load_options(),
        )
        return total, [_orm_to_entity(r) for r in rows]

    async def _reload(self, job_id: int) -> PrintJob:
        reloaded = (
            await self._db.scalars(by_id(PrintJobOrmModel, job_id, *_load_options(), refresh=True))
        ).one()
        return _orm_to_entity(reloaded)

    async def claim_for_event(self, item: PrintJob) -> PrintJob | None:
        """ON CONFLICT DO NOTHING on the partial unique
        (classifier, source_event_id) index, so of two deliveries of one
        event exactly one gets the row back."""
        dialect = self._db.get_bind().dialect.name
        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        claimed_id = await self._db.scalar(
            insert(PrintJobOrmModel)
            .values(**_entity_to_dict(item))
            .on_conflict_do_nothing(
                index_elements=["classifier", "source_event_id"],
                index_where=PrintJobOrmModel.source_event_id.is_not(None),
            )
            .returning(PrintJobOrmModel.id)
        )
        if claimed_id is None:
            return None
        return await self._reload(claimed_id)

    async def finish_claimed(self, item: PrintJob) -> PrintJob:
        await self._db.execute(
            update(PrintJobOrmModel)
            .where(PrintJobOrmModel.id == item.id)
            .values(
                template_id=item.template_id,
                printer_id=item.printer_id,
                copies=item.copies,
                status=item.status.value,
                error_message=item.error_message,
                rendered_zpl=item.rendered_zpl,
                document_bytes=item.document_bytes,
            )
            .execution_options(synchronize_session=False)
        )
        return await self._reload(item.id)

    async def release_claim(self, job_id: int) -> None:
        await self._db.execute(
            delete(PrintJobOrmModel)
            .where(
                PrintJobOrmModel.id == job_id,
                PrintJobOrmModel.status == PrintJobStatus.PRINTING.value,
            )
            .execution_options(synchronize_session=False)
        )


def _job_classifier(stored: str) -> PrintClassifier | UploadedPrintDocument:
    """A job's classifier column holds a template classifier or, for a
    report the browser uploads, the document it printed."""
    try:
        return PrintClassifier(stored)
    except ValueError:
        return UploadedPrintDocument(stored)
