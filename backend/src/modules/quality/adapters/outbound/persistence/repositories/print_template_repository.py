"""
Concrete implementation of IPrintTemplateRepository using SQLAlchemy + Postgres.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.quality.adapters.outbound.persistence.models.print_template_model import (
    PrintTemplateOrmModel,
)
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences. Built on first call rather
    than at import, because constructing a loader option configures the mapper
    registry before every model module is registered."""
    return (
        load_user(PrintTemplateOrmModel.creator),
        load_user(PrintTemplateOrmModel.changed_by),
        selectinload(PrintTemplateOrmModel.printer),
    )


def _orm_to_entity(orm: PrintTemplateOrmModel) -> PrintTemplate:
    return PrintTemplate(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        classifier=PrintClassifier(orm.classifier),
        trigger=PrintTrigger(orm.trigger) if orm.trigger is not None else None,
        source=orm.source,
        field_map=dict(orm.field_map or {}),
        printer_id=orm.printer_id,
        auto_print=orm.auto_print,
        copies_rule=PrintCopiesRule(orm.copies_rule),
        copies_fixed=orm.copies_fixed,
        max_copies=orm.max_copies,
        design_dpi=orm.design_dpi,
        label_width_mm=orm.label_width_mm,
        label_height_mm=orm.label_height_mm,
        paper=orm.paper,
        enabled=orm.enabled,
        note=orm.note,
        creator_id=orm.creator_id,
        creator_full_name=orm.creator.full_name if orm.creator else "",
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        printer_name=orm.printer.name if orm.printer else "",
    )


def _entity_to_dict(item: PrintTemplate) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "classifier": item.classifier.value,
        "trigger": item.trigger.value if item.trigger is not None else None,
        "source": item.source,
        "field_map": item.field_map,
        "printer_id": item.printer_id,
        "auto_print": item.auto_print,
        "copies_rule": item.copies_rule.value,
        "copies_fixed": item.copies_fixed,
        "max_copies": item.max_copies,
        "design_dpi": item.design_dpi,
        "label_width_mm": item.label_width_mm,
        "label_height_mm": item.label_height_mm,
        "paper": item.paper,
        "enabled": item.enabled,
        "note": item.note,
        "creator_id": item.creator_id,
    }


class SqlAlchemyPrintTemplateRepository:
    """Implements IPrintTemplateRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_classifier(self, classifier: str) -> PrintTemplate | None:
        orm = await self._db.scalar(
            select(PrintTemplateOrmModel)
            .where(PrintTemplateOrmModel.classifier == classifier)
            .options(*_load_options())
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_all(self) -> list[PrintTemplate]:
        rows = (
            await self._db.scalars(
                select(PrintTemplateOrmModel)
                .options(*_load_options())
                .order_by(PrintTemplateOrmModel.id)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_armed_by_trigger(self, trigger: str) -> list[PrintTemplate]:
        rows = (
            await self._db.scalars(
                select(PrintTemplateOrmModel)
                .where(
                    PrintTemplateOrmModel.trigger == trigger,
                    PrintTemplateOrmModel.auto_print.is_(True),
                    PrintTemplateOrmModel.enabled.is_(True),
                    PrintTemplateOrmModel.printer_id.isnot(None),
                )
                .options(*_load_options())
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def save(self, item: PrintTemplate) -> PrintTemplate:
        if item.id == 0:
            existing = PrintTemplateOrmModel(**_entity_to_dict(item))
            self._db.add(existing)
        else:
            found = await self._db.scalar(
                select(PrintTemplateOrmModel).where(PrintTemplateOrmModel.id == item.id).limit(1)
            )
            if not found:
                raise ValueError(f"PrintTemplateOrmModel id={item.id} not found.")
            existing = found
            for k, v in _entity_to_dict(item).items():
                setattr(existing, k, v)
        await self._db.flush()
        reloaded = (
            await self._db.scalars(
                select(PrintTemplateOrmModel)
                .where(PrintTemplateOrmModel.id == existing.id)
                .options(*_load_options())
                .execution_options(populate_existing=True)
            )
        ).one()
        return _orm_to_entity(reloaded)
