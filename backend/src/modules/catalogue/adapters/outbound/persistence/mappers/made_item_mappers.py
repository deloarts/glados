"""
ORM <-> domain entity mapping helpers for the MadeItem aggregate. Not part of
the public API of this package.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption
from sqlalchemy.orm.strategy_options import _AbstractLoad

from src.modules.catalogue.adapters.outbound.persistence.mappers.bought_item_mappers import (
    item_orm_to_entity as bought_item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    article_group_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.source_item_mappers import (
    source_item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_process_model import (
    MadeItemProcessOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.infrastructure.label_languages import resolve_label

# ── MadeItem ──────────────────────────────────────────────────────────


def item_load_options(item: Any) -> tuple[_AbstractLoad, ...]:
    """Every relationship item_orm_to_entity traverses, eager-loaded. `item`
    is the made-item entity the query selects, which is an aliased class
    when the statement ranks revisions in a subquery. Typed as loader
    options rather than ORMOption so a parent can nest them under its own
    relationship with `.options()`."""
    return (
        load_user(item.creator),
        load_user(item.changed_by),
        load_user(item.bought_item, BoughtItemOrmModel.creator),
        load_user(item.bought_item, BoughtItemOrmModel.changed_by),
        selectinload(item.bought_item).selectinload(BoughtItemOrmModel.manufacturer),
        selectinload(item.bought_item).selectinload(BoughtItemOrmModel.product_family),
        load_user(
            item.bought_item, BoughtItemOrmModel.article_groups, ArticleGroupOrmModel.creator
        ),
        load_user(
            item.bought_item, BoughtItemOrmModel.article_groups, ArticleGroupOrmModel.changed_by
        ),
        load_user(item.source_item, SourceItemOrmModel.creator),
        load_user(item.source_item, SourceItemOrmModel.changed_by),
        selectinload(item.source_item).selectinload(SourceItemOrmModel.manufacturer),
        selectinload(item.source_item).selectinload(SourceItemOrmModel.type),
        selectinload(item.customer),
        load_user(item.article_groups, ArticleGroupOrmModel.creator),
        load_user(item.article_groups, ArticleGroupOrmModel.changed_by),
        selectinload(item.processes).selectinload(MadeItemProcessOrmModel.fabrication_method),
        selectinload(item.processes).selectinload(MadeItemProcessOrmModel.inspection_method),
    )


@lru_cache(maxsize=1)
def made_item_load_options() -> tuple[_AbstractLoad, ...]:
    """item_load_options for the plain model, built on first use rather than
    at import so the mapper registry is only configured once every model is
    imported."""
    return item_load_options(MadeItemOrmModel)


def _item_source_label(orm: MadeItemOrmModel) -> str:
    if orm.bought_item:
        return orm.bought_item.article_name
    if orm.source_item:
        return orm.source_item.dimension or f"Source item #{orm.source_item.id}"
    return ""


def _item_source_sublabel(orm: MadeItemOrmModel) -> str:
    if orm.bought_item:
        return orm.bought_item.order_code_1
    if orm.source_item:
        type_name = resolve_label(orm.source_item.type.name) if orm.source_item.type else None
        return " | ".join(part for part in (orm.source_item.material, type_name) if part)
    return ""


def item_orm_to_entity(orm: MadeItemOrmModel) -> MadeItem:
    return MadeItem(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        revision=orm.revision,
        revision_date=orm.revision_date,
        revision_note=orm.revision_note,
        article_name=orm.article_name,
        status=MadeItemCatalogueStatus(orm.status),
        data_source=DataSource(orm.data_source),
        part_number=orm.part_number,
        material=orm.material,
        mass=orm.mass,
        base_size=orm.base_size,
        note=orm.note,
        weblink=orm.weblink,
        customer_id=orm.customer_id,
        customer_part_number=orm.customer_part_number,
        customer_revision=orm.customer_revision,
        customer_name=orm.customer.name if orm.customer else None,
        files=[],  # files loaded separately if needed
        **creator_kwargs(orm.creator_id, orm.creator),
        changed_by_id=orm.changed_by_id,
        approver_id=orm.approver_id,
        bought_item_id=orm.bought_item_id,
        source_item_id=orm.source_item_id,
        article_group_ids=[g.id for g in orm.article_groups],
        successor_item_id=orm.successor_item_id,
        vault_id=orm.vault_id,
        pdm_file_id=orm.pdm_file_id,
        pdm_file_version=orm.pdm_file_version,
        pdm_synced_at=utc_aware(orm.pdm_synced_at),
        pdm_sync_state=_pdm_sync_state(orm.pdm_sync_state),
        pdm_source_item_id=orm.pdm_source_item_id,
        changed_by=user_orm_to_entity(orm.changed_by) if orm.changed_by else None,
        bought_item=bought_item_orm_to_entity(orm.bought_item) if orm.bought_item else None,
        source_item=source_item_orm_to_entity(orm.source_item) if orm.source_item else None,
        article_groups=[article_group_orm_to_entity(g) for g in orm.article_groups],
        processes=[process_orm_to_entity(p) for p in orm.processes],
        source_label=_item_source_label(orm),
        source_sublabel=_item_source_sublabel(orm),
        edit_version=orm.edit_version,
    )


def item_entity_to_dict(item: MadeItem) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "archived": item.archived,
        "revision": item.revision,
        "revision_date": item.revision_date,
        "revision_note": item.revision_note,
        "article_name": item.article_name,
        "status": item.status.value,
        "data_source": item.data_source.value,
        "part_number": item.part_number,
        "material": item.material,
        "mass": item.mass,
        "base_size": item.base_size,
        "note": item.note,
        "weblink": item.weblink,
        "customer_id": item.customer_id,
        "customer_part_number": item.customer_part_number,
        "customer_revision": item.customer_revision,
        "creator_id": item.creator_id,
        "changed_by_id": item.changed_by_id,
        "approver_id": item.approver_id,
        "bought_item_id": item.bought_item_id,
        "source_item_id": item.source_item_id,
        "successor_item_id": item.successor_item_id,
        "vault_id": item.vault_id,
        "pdm_file_id": item.pdm_file_id,
        "pdm_file_version": item.pdm_file_version,
        "pdm_synced_at": item.pdm_synced_at,
        "pdm_sync_state": item.pdm_sync_state.value if item.pdm_sync_state else None,
        "pdm_source_item_id": item.pdm_source_item_id,
    }


# ── MadeItemProcess ───────────────────────────────────────────────────


@lru_cache(maxsize=1)
def process_load_options() -> tuple[ORMOption, ...]:
    return (
        selectinload(MadeItemProcessOrmModel.fabrication_method),
        selectinload(MadeItemProcessOrmModel.inspection_method),
    )


def process_orm_to_entity(orm: MadeItemProcessOrmModel) -> MadeItemProcess:
    return MadeItemProcess(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        note=orm.note,
        estimated_setup_minutes=orm.estimated_setup_minutes,
        estimated_minutes_per_piece=orm.estimated_minutes_per_piece,
        creator_id=orm.creator_id,
        fabrication_method_id=orm.fabrication_method_id,
        made_item_id=orm.made_item_id,
        position=orm.position,
        group_index=orm.group_index,
        role=StepRole(orm.role),
        inspection_method_id=orm.inspection_method_id,
        fabrication_method_name=(
            LocalizedText(values=dict(orm.fabrication_method.name or {}))
            if orm.fabrication_method
            else LocalizedText()
        ),
        inspection_method_name=(
            LocalizedText(values=dict(orm.inspection_method.name or {}))
            if orm.inspection_method
            else None
        ),
    )


def process_entity_to_dict(process: MadeItemProcess) -> dict[str, Any]:
    return {
        "created": process.created,
        "note": process.note,
        "estimated_setup_minutes": process.estimated_setup_minutes,
        "estimated_minutes_per_piece": process.estimated_minutes_per_piece,
        "creator_id": process.creator_id,
        "fabrication_method_id": process.fabrication_method_id,
        "made_item_id": process.made_item_id,
        "position": process.position,
        "group_index": process.group_index,
        "role": process.role.value,
        "inspection_method_id": process.inspection_method_id,
    }


def _pdm_sync_state(stored: str | None) -> PdmSyncState | None:
    return PdmSyncState(stored) if stored is not None else None
