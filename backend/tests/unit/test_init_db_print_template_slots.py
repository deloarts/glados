"""
InitDatabase creates one unconfigured print template slot per classifier at
startup and never touches a slot that already exists, so an admin's
configuration survives every restart and a classifier added to the registry
gets its slot on the next start.
"""

import importlib

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind


async def _engine() -> AsyncEngine:
    for name in model_module_names():
        importlib.import_module(name)
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def _boot(sessions: async_sessionmaker) -> None:  # type: ignore[type-arg]
    async with sessions() as db:
        await InitDatabase(
            user_repo=SqlAlchemyUserRepository(db),
            admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
            print_template_repo=SqlAlchemyPrintTemplateRepository(db),
            db=db,
        ).run()


async def test_every_classifier_gets_an_unconfigured_slot():
    engine = await _engine()
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    await _boot(sessions)

    async with sessions() as db:
        templates = await SqlAlchemyPrintTemplateRepository(db).get_all()

    assert sorted(t.classifier for t in templates) == sorted(CLASSIFIERS)
    for template in templates:
        spec = CLASSIFIERS[template.classifier]
        assert template.enabled is False
        assert template.source is None
        assert template.field_map == {}
        assert template.printer_id is None
        assert template.auto_print is False
        assert template.trigger == spec.default_trigger
        expected_paper = "a4" if spec.output_kind == PrintOutputKind.PDF_DOCKET else None
        assert template.paper == expected_paper


async def test_a_second_start_leaves_an_edited_slot_alone():
    engine = await _engine()
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    await _boot(sessions)

    async with sessions() as db:
        repo = SqlAlchemyPrintTemplateRepository(db)
        scrap_tag = await repo.get_by_classifier(PrintClassifier.SCRAP_TAG.value)
        assert scrap_tag is not None
        scrap_tag.source = "^XA^FDedited^FS^XZ"
        scrap_tag.enabled = True
        await repo.save(scrap_tag)
        await db.commit()

    await _boot(sessions)

    async with sessions() as db:
        templates = await SqlAlchemyPrintTemplateRepository(db).get_all()
    assert len(templates) == len(CLASSIFIERS)
    edited = next(t for t in templates if t.classifier == PrintClassifier.SCRAP_TAG)
    assert edited.source == "^XA^FDedited^FS^XZ"
    assert edited.enabled is True
