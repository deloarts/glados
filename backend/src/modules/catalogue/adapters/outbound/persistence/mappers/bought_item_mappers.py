"""
ORM <-> domain entity mapping helpers shared by the bought-item aggregate
repositories in this package. Not part of the public API of this package,
each repository module imports only the mappers it needs.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    article_group_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_file_model import (
    BoughtItemFileOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.product_family_mappers import (
    product_family_ref_orm_to_entity,
)
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    file_orm_to_entity,
)
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user

# ── BoughtItem ────────────────────────────────────────────────────────


# Every relationship item_orm_to_entity reads, including the article group
# creator that article_group_orm_to_entity resolves. The models default to
# lazy="raise_on_sql", so each select whose rows reach the mapper names its
# loads explicitly through this function. Built lazily, since constructing a
# loader option configures the mappers, which needs every model registered.
@lru_cache(maxsize=1)
def bought_item_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(BoughtItemOrmModel.creator),
        load_user(BoughtItemOrmModel.changed_by),
        selectinload(BoughtItemOrmModel.manufacturer),
        selectinload(BoughtItemOrmModel.product_family),
        load_user(BoughtItemOrmModel.article_groups, ArticleGroupOrmModel.creator),
        load_user(BoughtItemOrmModel.article_groups, ArticleGroupOrmModel.changed_by),
    )


def item_file_orm_to_entity(orm: BoughtItemFileOrmModel) -> BoughtItemFile:
    return file_orm_to_entity(orm, BoughtItemFile, BoughtItemFileCategory, "bought_item_id")


def item_orm_to_entity(
    orm: BoughtItemOrmModel,
    pdf_files: list[BoughtItemFile] | None = None,
) -> BoughtItem:
    return BoughtItem(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        order_code_1=orm.order_code_1,
        order_code_2=orm.order_code_2,
        gtin=orm.gtin,
        ean=orm.ean,
        tariff_number=orm.tariff_number,
        status=BoughtItemCatalogueStatus(orm.status),
        article_name=orm.article_name,
        data_source=DataSource(orm.data_source),
        part_number=orm.part_number,
        revision=orm.revision,
        mass=orm.mass,
        successor_item_id=orm.successor_item_id,
        article_group_ids=[g.id for g in orm.article_groups],
        note=orm.note,
        weblink=orm.weblink,
        files=[],  # files loaded separately if needed
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        approver_id=orm.approver_id,
        manufacturer_id=orm.manufacturer_id,
        product_family_id=orm.product_family_id,
        over_delivery_tolerance_percent=orm.over_delivery_tolerance_percent,
        under_delivery_tolerance_percent=orm.under_delivery_tolerance_percent,
        edp_part_id=orm.edp_part_id,
        edp_synced_at=utc_aware(orm.edp_synced_at),
        pdm_edp_part_id=orm.pdm_edp_part_id,
        vault_id=orm.vault_id,
        pdm_file_id=orm.pdm_file_id,
        pdm_file_version=orm.pdm_file_version,
        pdm_synced_at=utc_aware(orm.pdm_synced_at),
        pdm_sync_state=_pdm_sync_state(orm.pdm_sync_state),
        manufacturer_name=orm.manufacturer.name if orm.manufacturer else "",
        article_groups=[article_group_orm_to_entity(g) for g in orm.article_groups],
        product_family=(
            product_family_ref_orm_to_entity(orm.product_family) if orm.product_family else None
        ),
        pdf_files=pdf_files or [],
        edit_version=orm.edit_version,
    )


def item_entity_to_dict(item: BoughtItem) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "archived": item.archived,
        "order_code_1": item.order_code_1,
        "order_code_2": item.order_code_2,
        "gtin": item.gtin,
        "ean": item.ean,
        "tariff_number": item.tariff_number,
        "status": item.status.value,
        "article_name": item.article_name,
        "data_source": item.data_source.value,
        "part_number": item.part_number,
        "mass": item.mass,
        "successor_item_id": item.successor_item_id,
        "note": item.note,
        "weblink": item.weblink,
        "creator_id": item.creator_id,
        "approver_id": item.approver_id,
        "manufacturer_id": item.manufacturer_id,
        "product_family_id": item.product_family_id,
        "over_delivery_tolerance_percent": item.over_delivery_tolerance_percent,
        "under_delivery_tolerance_percent": item.under_delivery_tolerance_percent,
        "edp_part_id": item.edp_part_id,
        "edp_synced_at": item.edp_synced_at,
        "pdm_edp_part_id": item.pdm_edp_part_id,
        "vault_id": item.vault_id,
        "pdm_file_id": item.pdm_file_id,
        "pdm_file_version": item.pdm_file_version,
        "pdm_synced_at": item.pdm_synced_at,
        "pdm_sync_state": item.pdm_sync_state.value if item.pdm_sync_state else None,
    }


# ── DemandItem ────────────────────────────────────────────────────────


def _pdm_sync_state(stored: str | None) -> PdmSyncState | None:
    return PdmSyncState(stored) if stored is not None else None
