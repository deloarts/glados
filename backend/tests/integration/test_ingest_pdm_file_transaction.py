"""
Runs IngestPdmFile against the real repositories and the throwaway SQLite
database to prove that an in-place update which replaces the routing
(the "processes: update in place" policy) is one transaction: when a later
write of the same ingest fails, the old process steps are still there.
"""

import dataclasses
import json
from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.workers.pdm_schedule import build_ingest_pdm_file
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.policies.item_field_ownership import RevisionFieldPolicy
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.value_objects.localized_text import LocalizedText

_RELEASED_STATE_ID = 10
_MADE_VARIABLE_MAP = {
    "part_number": "PDM.PartNumber",
    "revision": "PDM.Revision",
    "article_name": "Glados.ArticleName",
    "note": "Glados.Note",
    "processes": "Glados.Processes",
}


async def _arrange(db: AsyncSession, creator_id: int) -> tuple[int, int]:
    """Configures PDM ingest with processes updated in place and stores a
    PDM-linked made item with one routing step. Returns the made item id and
    a second fabrication method id for the new routing."""
    await db.commit()
    settings_repo = SqlAlchemyAdminSettingsRepository(db)
    pdm = await settings_repo.get_pdm()
    await settings_repo.save_pdm(
        dataclasses.replace(
            pdm,
            enabled=True,
            made_item_variable_map=dict(_MADE_VARIABLE_MAP),
            made_released_state_ids=[_RELEASED_STATE_ID],
        )
    )
    await db.commit()
    made_settings = await settings_repo.get_made_items()
    policy = [
        RevisionFieldPolicy(
            field=p.field,
            web_requires_revision=p.web_requires_revision,
            pdm_update_in_place=p.pdm_update_in_place or p.field == "processes",
        )
        for p in default_policy()
    ]
    await settings_repo.save_made_items(
        dataclasses.replace(
            made_settings, pdm_part_number_pattern=r"CAD-\d+", revision_field_policy=policy
        )
    )
    await db.commit()

    methods = SqlAlchemyFabricationMethodRepository(db)
    old_method, new_method = [
        await methods.save(
            FabricationMethod(
                id=0,
                created=datetime.now(UTC),
                changed=datetime.now(UTC),
                changes=[],
                archived=False,
                name=LocalizedText({"enGB": name}),
                label_color="#000000",
                label_font_color="#ffffff",
                description=LocalizedText(),
                creator_id=creator_id,
            )
        )
        for name in ("Milling", "Turning")
    ]

    items = SqlAlchemyMadeItemRepository(db)
    item = await items.save(
        MadeItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            revision="A",
            revision_date=None,
            revision_note=None,
            article_name="Bracket",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.CAD,
            part_number="CAD-1001",
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
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
    )
    await items.save_process(
        MadeItemProcess(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            note="old step",
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            creator_id=creator_id,
            fabrication_method_id=old_method.id,
            made_item_id=item.id,
            position=0,
            group_index=0,
        )
    )
    await db.commit()
    return item.id, new_method.id


def _payload(new_method_id: int) -> PdmFilePayload:
    return PdmFilePayload(
        vault_id="V1",
        file_id=100,
        file_version=2,
        path="\\Made\\part.sldprt",
        name="part.sldprt",
        parent_folder_id=1,
        state_id=_RELEASED_STATE_ID,
        state="Released",
        kind="made",
        variables={
            "PDM.PartNumber": "CAD-1001",
            "PDM.Revision": "A",
            "Glados.ArticleName": "Bracket",
            "Glados.Note": "from CAD",
            "Glados.Processes": json.dumps(
                [{"role": "fabrication", "fabrication_method_id": new_method_id}]
            ),
        },
        modified_at=None,
    )


async def _ingest(payload: PdmFilePayload) -> None:
    async with SessionLocal() as session:
        pdm_session = PdmSessionService(
            repo=SqlAlchemyAdminSettingsRepository(session),
            gateway_factory=lambda connection: None,  # type: ignore[arg-type,return-value]
        )
        await build_ingest_pdm_file(session, pdm_session).execute(payload)


async def _process_notes(made_item_id: int) -> list[str | None]:
    async with SessionLocal() as session:
        processes = await SqlAlchemyMadeItemRepository(session).get_processes(made_item_id)
        return [p.note for p in processes]


async def test_failed_in_place_update_keeps_the_old_routing(
    db: AsyncSession, create_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    system_user = await create_user(SYSTEM_USER, "system@example.com", is_systemuser=True)
    made_item_id, new_method_id = await _arrange(db, system_user.id)

    async def _explode(self: object, items: object) -> None:
        raise RuntimeError("snapshot upsert exploded")

    monkeypatch.setattr(SqlAlchemyPdmFileSnapshotRepository, "upsert_many", _explode)

    with pytest.raises(RuntimeError, match="snapshot upsert exploded"):
        await _ingest(_payload(new_method_id))

    assert await _process_notes(made_item_id) == ["old step"]


async def test_successful_in_place_update_replaces_the_routing(
    db: AsyncSession, create_user
) -> None:
    system_user = await create_user(SYSTEM_USER, "system@example.com", is_systemuser=True)
    made_item_id, new_method_id = await _arrange(db, system_user.id)

    await _ingest(_payload(new_method_id))

    async with SessionLocal() as session:
        processes = await SqlAlchemyMadeItemRepository(session).get_processes(made_item_id)
    assert [(p.fabrication_method_id, p.note) for p in processes] == [(new_method_id, None)]
